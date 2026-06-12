import io
import ipaddress
import logging
import socket
import time
from urllib.parse import urlparse

import pandas as pd
import requests
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from PIL import Image
from rest_framework.exceptions import ValidationError

from inventory.models import Inventory
from .models import Brand, Category, Product, ProductImage, ProductSpecification

logger = logging.getLogger("bulk_upload")



def clean_str(value, default=None):
    if value is None:
        return default
    if pd.isna(value):
        return default
    s = str(value).strip()
    return s if s else default


def parse_boolean(value, default=False):
    if value is None or pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "y", "t")


def parse_int(value, default=0):
    if value is None or pd.isna(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def is_safe_url(url, allowed_schemes=("http", "https")):
    
    try:
        parsed = urlparse(url)
        if parsed.scheme not in allowed_schemes:
            return False, f"Disallowed scheme: {parsed.scheme}"
        if not parsed.hostname:
            return False, "Missing hostname"
        try:
            ip_str = socket.gethostbyname(parsed.hostname)
            ip = ipaddress.ip_address(ip_str)
        except (socket.gaierror, ValueError) as e:
            return False, f"DNS resolution failed: {e}"
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False, f"IP {ip} is in a restricted range"
        return True, None
    except Exception as e:
        return False, str(e)


def get_full_product_data(product):
    from .serializers import (
        ProductImageSerializer,
        ProductSerializer,
        ProductSpecificationSerializer,
    )
    data = ProductSerializer(product).data
    data["images"] = ProductImageSerializer(product.images.all(), many=True).data
    data["specifications"] = ProductSpecificationSerializer(
        product.specifications.all(), many=True
    ).data
    try:
        from inventory.serializers import InventorySerializer
        data["inventory"] = InventorySerializer(product.inventory).data
    except Exception:
        data["inventory"] = None
    return data



class BulkProductUploadService:
    REQUIRED_COLUMNS = ["product_name", "category", "sku", "description"]
    OPTIONAL_COLUMNS = [
        "brand", "mpn", "highlights", "price", "featured",
        "top_selling", "new_arrival", "is_active", "stock",
        "product_image", "image",
    ]
    MAX_FILE_SIZE_MB = 50
    MAX_ROWS = 1000
    MAX_IMAGE_SIZE_MB = 10
    DOWNLOAD_TIMEOUT_SECONDS = 10
    URL_VALIDATION_TIMEOUT_SECONDS = 5
    ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "GIF", "WEBP"}

    def __init__(self, excel_file, uploaded_images=None):
        self.excel_file = excel_file
        self.uploaded_images = {}
        if uploaded_images:
            for name, file_obj in uploaded_images.items():
                self.uploaded_images[name.lower()] = file_obj
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.failed_count = 0
        self.products_created = []
        self.start_time = time.time()
        self._url_validation_cache = {}


    def validate_excel_file(self):
        if not self.excel_file.name.lower().endswith((".xlsx", ".xls")):
            raise ValidationError("File must be Excel format (.xlsx or .xls)")
        size_mb = self.excel_file.size / (1024 * 1024)
        if size_mb > self.MAX_FILE_SIZE_MB:
            raise ValidationError(
                f"File size {size_mb:.1f}MB exceeds limit of {self.MAX_FILE_SIZE_MB}MB"
            )
        return True

    def read_excel_file(self):
        self.validate_excel_file()
        try:
            df = pd.read_excel(self.excel_file, sheet_name="Products")
        except ValueError as e:
            raise ValidationError(
                f"Could not read 'Products' sheet from Excel file: {e}"
            )
        except Exception as e:
            raise ValidationError(f"Error reading Excel file: {e}")
        missing_cols = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            raise ValidationError(
                f"Missing required columns: {', '.join(missing_cols)}"
            )
        if len(df) > self.MAX_ROWS:
            raise ValidationError(
                f"File has {len(df)} rows; limit is {self.MAX_ROWS}"
            )
        return df


    @classmethod
    def validate_image_url(cls, url):
        
        ok, reason = is_safe_url(url)
        if not ok:
            return False, reason
        try:
            response = requests.head(
                url,
                timeout=cls.URL_VALIDATION_TIMEOUT_SECONDS,
                allow_redirects=True,
            )
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                response = requests.get(
                    url,
                    timeout=cls.URL_VALIDATION_TIMEOUT_SECONDS,
                    headers={"Range": "bytes=0-1023"},
                    stream=True,
                )
                if response.status_code not in (200, 206):
                    return False, f"HTTP {response.status_code} on GET"
                content_type = response.headers.get("Content-Type", "").lower()
                response.close()
                if not content_type.startswith("image/"):
                    return False, f"Not an image (Content-Type: {content_type or 'missing'})"
            return True, None
        except requests.RequestException as e:
            return False, f"Request error: {type(e).__name__}"

    def _check_url(self, url):
        """Cached URL validation."""
        if url in self._url_validation_cache:
            return self._url_validation_cache[url]
        result = self.validate_image_url(url)
        self._url_validation_cache[url] = result
        return result


    @classmethod
    def download_image_from_url(cls, image_url):
        url = clean_str(image_url)
        if not url:
            return None

        ok, reason = is_safe_url(url)
        if not ok:
            logger.warning(f"Refusing unsafe URL '{url}': {reason}")
            return None

        try:
            with requests.get(
                url,
                timeout=cls.DOWNLOAD_TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "").lower()
                if not content_type.startswith("image/"):
                    logger.warning(
                        f"URL '{url}' returned non-image Content-Type: {content_type}"
                    )
                    return None

                max_bytes = cls.MAX_IMAGE_SIZE_MB * 1024 * 1024
                buffer = io.BytesIO()
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        logger.warning(
                            f"URL '{url}' exceeds {cls.MAX_IMAGE_SIZE_MB}MB limit"
                        )
                        return None
                    buffer.write(chunk)

                buffer.seek(0)
                try:
                    img = Image.open(buffer)
                    img.verify()
                except Exception as e:
                    logger.warning(f"URL '{url}' is not a valid image: {e}")
                    return None

                buffer.seek(0)
                img = Image.open(buffer)
                fmt = (img.format or "").upper()
                if fmt not in cls.ALLOWED_IMAGE_FORMATS:
                    logger.warning(f"URL '{url}' has disallowed format: {fmt}")
                    return None

                ext_map = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}
                mime_map = {
                    "JPEG": "image/jpeg",
                    "PNG": "image/png",
                    "GIF": "image/gif",
                    "WEBP": "image/webp",
                }
                ext = ext_map.get(fmt, "jpg")
                content_type_out = mime_map.get(fmt, "image/jpeg")

                path = urlparse(url).path
                base = path.rsplit("/", 1)[-1].split(".")[0] or "image"
                base = "".join(c for c in base if c.isalnum() or c in ("-", "_"))[:50]
                filename = f"product_{base or 'image'}.{ext}"

                buffer.seek(0)
                return InMemoryUploadedFile(
                    buffer,
                    "ImageField",
                    filename,
                    content_type_out,
                    downloaded,
                    None,
                )
        except requests.RequestException as e:
            logger.warning(f"Failed to download image from {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error downloading {url}: {e}")
            return None

    def get_image_file(self, image_reference):
        ref = clean_str(image_reference)
        if not ref:
            return None
        key = ref.lower()
        original = self.uploaded_images.get(key)
        if not original:
            key_no_ext = key.rsplit(".", 1)[0]
            for stored_key, stored_file in self.uploaded_images.items():
                if stored_key.rsplit(".", 1)[0] == key_no_ext:
                    original = stored_file
                    break
        if not original:
            return None
        try:
            original.seek(0)
            data = original.read()
            original.seek(0)
        except Exception as e:
            logger.warning(f"Could not read uploaded file '{ref}': {e}")
            return None
        buffer = io.BytesIO(data)
        return InMemoryUploadedFile(
            buffer,
            "ImageField",
            original.name,
            getattr(original, "content_type", "image/jpeg"),
            len(data),
            None,
        )


    @staticmethod
    def parse_specifications(spec_string):
        specifications = []
        cleaned = clean_str(spec_string)
        if not cleaned:
            return specifications
        try:
            sections = cleaned.split(";")
            for section_data in sections:
                if ":" not in section_data:
                    continue
                section_name, specs = section_data.split(":", 1)
                section_name = section_name.strip()
                if not section_name:
                    continue
                for pair in specs.split("|"):
                    if "=" not in pair:
                        continue
                    key, value = pair.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        specifications.append({
                            "section": section_name,
                            "key": key,
                            "value": value,
                        })
        except Exception as e:
            logger.warning(f"Failed to parse specifications: {e}")
        return specifications

    @staticmethod
    def get_or_create_category(category_name):
        name = clean_str(category_name)
        if not name:
            raise ValidationError("Category name is required")
        category, _ = Category.objects.get_or_create(name=name, parent=None)
        return category

    @staticmethod
    def get_or_create_subcategory(parent_category, subcategory_name):
        name = clean_str(subcategory_name)
        if not name:
            return None
        subcategory, _ = Category.objects.get_or_create(name=name, parent=parent_category)
        return subcategory

    @staticmethod
    def get_or_create_brand(brand_name):
        name = clean_str(brand_name)
        if not name:
            return None
        try:
            brand, _ = Brand.objects.get_or_create(name=name)
            return brand
        except Exception as e:
            logger.warning(f"Error with brand '{brand_name}': {e}")
            return None


    def _build_product_in_transaction(self, row, row_num):
        with transaction.atomic():
            category = self.get_or_create_category(row.get("category"))
            subcategory_name = (
                clean_str(row.get("subcategory"))
                or clean_str(row.get("sub_category"))
                or clean_str(row.get("subCategory"))
            )
            subcategory = self.get_or_create_subcategory(category, subcategory_name) if subcategory_name else None
            brand = self.get_or_create_brand(row.get("brand"))

            sku = clean_str(row.get("sku"))
            name = clean_str(row.get("product_name"))
            description = clean_str(row.get("description"))

            if not name:
                raise ValidationError("product_name is required")
            if not description:
                raise ValidationError("description is required")
            if sku and Product.objects.filter(sku=sku).exists():
                raise ValidationError(f"SKU '{sku}' already exists")

            product = Product.objects.create(
                name=name,
                category=category,
                subcategory=subcategory,
                brand=brand,
                sku=sku,
                mpn=clean_str(row.get("mpn")),
                description=description,
                highlights=clean_str(row.get("highlights")),
                featured=parse_boolean(row.get("featured")),
                top_selling=parse_boolean(row.get("top_selling")),
                new_arrival=parse_boolean(row.get("new_arrival")),
                is_active=parse_boolean(row.get("is_active"), default=True),
            )

            main_image_ref = (
                clean_str(row.get("product_image"))
                or clean_str(row.get("image"))
                or clean_str(row.get("image_1"))
            )
            if main_image_ref:
                if main_image_ref.lower().startswith(("http://", "https://")):
                    valid, reason = self._check_url(main_image_ref)
                    if valid:
                        image_file = self.download_image_from_url(main_image_ref)
                        if image_file:
                            product.product_image = image_file
                            product.save(update_fields=["product_image"])
                    else:
                        msg = f"Row {row_num}: main image URL unreachable ({reason}): {main_image_ref}"
                        self.warnings.append(msg)
                        logger.warning(msg)
                else:
                    image_file = self.get_image_file(main_image_ref)
                    if image_file:
                        product.product_image = image_file
                        product.save(update_fields=["product_image"])
                    else:
                        msg = f"Row {row_num}: main image '{main_image_ref}' not found in uploaded files"
                        self.warnings.append(msg)
                        logger.warning(msg)

            stock = parse_int(row.get("stock"), default=0)
            Inventory.objects.create(product=product, stock=stock)

            image_columns = [c for c in row.index if str(c).startswith("image_")]
            urls_to_download = []
            urls_failed = []
            for col in image_columns:
                ref = clean_str(row.get(col))
                if not ref:
                    continue
                if ref == main_image_ref:
                    continue
                if ref.lower().startswith(("http://", "https://")):
                    valid, reason = self._check_url(ref)
                    if valid:
                        urls_to_download.append(ref)
                    else:
                        urls_failed.append((ref, reason))
                else:
                    image_file = self.get_image_file(ref)
                    if image_file:
                        ProductImage.objects.create(product=product, image=image_file)
                        if not product.product_image:
                            fresh = self.get_image_file(ref)
                            if fresh:
                                product.product_image = fresh
                                product.save(update_fields=["product_image"])
                    else:
                        msg = f"Row {row_num}: image '{ref}' not found in uploaded files"
                        self.warnings.append(msg)
                        logger.warning(msg)

            for failed_url, reason in urls_failed:
                msg = f"Row {row_num}: image URL unreachable ({reason}): {failed_url}"
                self.warnings.append(msg)
                logger.warning(msg)

            spec_columns = [c for c in row.index if str(c).startswith("specs_")]
            for col in spec_columns:
                specs_string = clean_str(row.get(col))
                if not specs_string:
                    continue
                for spec in self.parse_specifications(specs_string):
                    ProductSpecification.objects.create(
                        product=product,
                        section=spec["section"],
                        key=spec["key"],
                        value=spec["value"],
                    )

            if urls_to_download:
                from .tasks import download_product_images_task
                product_id = product.id
                transaction.on_commit(
                    lambda: download_product_images_task.delay(
                        product_id, urls_to_download
                    )
                )

            return product

    def process_row(self, row, row_num):
        try:
            product = self._build_product_in_transaction(row, row_num)
        except ValidationError as e:
            detail = e.detail if hasattr(e, "detail") else str(e)
            msg = f"Row {row_num}: {detail}"
            self.errors.append(msg)
            self.failed_count += 1
            logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Row {row_num}: {e}"
            self.errors.append(msg)
            self.failed_count += 1
            logger.error(msg, exc_info=True)
            return False, msg

        self.success_count += 1
        try:
            self.products_created.append(get_full_product_data(product))
        except Exception as e:
            logger.warning(f"Could not serialize created product {product.id}: {e}")
        return True, None


    def upload(self):
        try:
            df = self.read_excel_file()
            if df.empty:
                raise ValidationError("Excel file is empty")

            for idx, row in df.iterrows():
                self.process_row(row, idx + 2)

            return {
                "success": True,
                "total_rows": len(df),
                "successful": self.success_count,
                "failed": self.failed_count,
                "errors": self.errors,
                "warnings": self.warnings,
                "products_created": self.products_created,
                "duration_seconds": round(time.time() - self.start_time, 2),
            }
        except ValidationError as e:
            return {
                "success": False,
                "message": str(e.detail if hasattr(e, "detail") else e),
                "errors": self.errors,
                "warnings": self.warnings,
            }
        except Exception as e:
            error_msg = f"Unexpected error during upload: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "message": error_msg,
                "errors": self.errors + [error_msg],
                "warnings": self.warnings,
            }