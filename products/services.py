import io
import logging
import socket
import time
from urllib.request import urlopen

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
import pandas as pd
from PIL import Image
from rest_framework.exceptions import ValidationError

from inventory.models import Inventory
from .models import Brand, Category, Product, ProductImage, ProductSpecification

logger = logging.getLogger('bulk_upload')
socket.setdefaulttimeout(10)

class BulkProductUploadService:
    REQUIRED_COLUMNS = ['product_name', 'category', 'sku', 'description']
    OPTIONAL_COLUMNS = [
        'brand', 'mpn', 'highlights', 'price', 'featured', 
        'top_selling', 'new_arrival', 'is_active', 'stock'
    ]
    MAX_FILE_SIZE_MB = 50
    MAX_ROWS = 1000
    IMAGE_TIMEOUT = 10
    
    def __init__(self, excel_file, uploaded_images=None):
        self.excel_file = excel_file
        self.uploaded_images = uploaded_images or {}
        self.errors = []
        self.success_count = 0
        self.failed_count = 0
        self.products_created = []
        self.start_time = time.time()
        
    def validate_excel_file(self):
        try:
            if not self.excel_file.name.endswith(('.xlsx', '.xls')):
                raise ValidationError("File must be Excel format (.xlsx or .xls)")
            return True
        except Exception as e:
            raise ValidationError(f"Invalid Excel file: {str(e)}")
    
    def read_excel_file(self):
        try:
            self.validate_excel_file()
            df = pd.read_excel(self.excel_file, sheet_name='Products')
            missing_cols = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
            if missing_cols:
                raise ValidationError(f"Missing required columns: {', '.join(missing_cols)}")
            return df
        except Exception as e:
            raise ValidationError(f"Error reading Excel file: {str(e)}")
    
    @staticmethod
    def download_image_from_url(image_url):
        try:
            if not image_url or pd.isna(image_url):
                return None
            response = urlopen(str(image_url))
            image_data = response.read()
            img = Image.open(io.BytesIO(image_data))
            img.verify()
            image_file = io.BytesIO(image_data)
            filename = f"product_{image_url.split('/')[-1].split('?')[0]}.jpg"
            return InMemoryUploadedFile(
                image_file,
                'ImageField',
                filename,
                'image/jpeg',
                len(image_data),
                None
            )
        except Exception as e:
            logger.warning(f"Failed to download image from {image_url}: {str(e)}")
            return None
    
    def get_image_file(self, image_reference):
        if not image_reference or pd.isna(image_reference):
            return None
        image_reference = str(image_reference).strip()
        if self.uploaded_images and image_reference in self.uploaded_images:
            return self.uploaded_images[image_reference]
        logger.warning(f"Image reference '{image_reference}' not found in URLs or uploaded files.")
        return None
        
    @staticmethod
    def parse_specifications(spec_string):
        specifications = []
        if not spec_string or pd.isna(spec_string):
            return specifications
        try:
            sections = str(spec_string).split(';')
            for section_data in sections:
                if ':' not in section_data:
                    continue
                section_name, specs = section_data.split(':', 1)
                section_name = section_name.strip()
                spec_pairs = specs.split('|')
                for pair in spec_pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        specifications.append({
                            'section': section_name.strip(),
                            'key': key.strip(),
                            'value': value.strip()
                        })
        except Exception as e:
            logger.warning(f"Failed to parse specifications: {str(e)}")
        return specifications
    
    @staticmethod
    def get_or_create_category(category_name):
        if not category_name or pd.isna(category_name):
            raise ValidationError("Category name is required")
        try:
            category, _ = Category.objects.get_or_create(
                name=str(category_name).strip()
            )
            return category
        except Exception as e:
            raise ValidationError(f"Error with category '{category_name}': {str(e)}")
    
    @staticmethod
    def get_or_create_brand(brand_name):
        if not brand_name or pd.isna(brand_name):
            return None
        try:
            brand, _ = Brand.objects.get_or_create(
                name=str(brand_name).strip()
            )
            return brand
        except Exception as e:
            logger.warning(f"Error with brand '{brand_name}': {str(e)}")
            return None
    
    @staticmethod
    def parse_boolean(value):
        if pd.isna(value):
            return False
        return str(value).lower() in ['true', '1', 'yes', 'y']
    
    @transaction.atomic
    def process_row(self, row, row_num):
        try:
            category = self.get_or_create_category(row.get('category'))
            brand = None
            if 'brand' in row:
                brand = self.get_or_create_brand(row.get('brand'))
            product = Product.objects.create(
                name=str(row['product_name']).strip(),
                category=category,
                brand=brand,
                sku=str(row.get('sku', '')).strip(),
                mpn=str(row.get('mpn', '')).strip() if 'mpn' in row else None,
                description=str(row['description']).strip(),
                highlights=str(row.get('highlights', '')).strip() if 'highlights' in row else None,
                featured=self.parse_boolean(row.get('featured', False)),
                top_selling=self.parse_boolean(row.get('top_selling', False)),
                new_arrival=self.parse_boolean(row.get('new_arrival', False)),
                is_active=self.parse_boolean(row.get('is_active', True))
            )
            stock = row.get('stock', 0)
            if stock and not pd.isna(stock):
                try:
                    stock = int(stock)
                except:
                    stock = 0
            Inventory.objects.create(product=product, stock=stock)
            image_columns = [col for col in row.index if col.startswith('image_')]
            image_urls_to_download = []
            for col in image_columns:
                image_ref = row.get(col)
                if image_ref and not pd.isna(image_ref):
                    image_ref = str(image_ref).strip()
                    if image_ref.startswith(('http://', 'https://')):
                        image_urls_to_download.append(image_ref)
                    else:
                        image_file = self.get_image_file(image_ref)
                        if image_file:
                            ProductImage.objects.create(
                                product=product,
                                image=image_file
                            )
            if image_urls_to_download:
                from .tasks import download_product_images_task
                from django.db import transaction
                transaction.on_commit(
                    lambda: download_product_images_task.delay(product.id, image_urls_to_download)
                )
            spec_columns = [col for col in row.index if col.startswith('specs_')]
            for col in spec_columns:
                specs_string = row.get(col)
                if specs_string and not pd.isna(specs_string):
                    specifications = self.parse_specifications(specs_string)
                    for spec in specifications:
                        ProductSpecification.objects.create(
                            product=product,
                            section=spec['section'],
                            key=spec['key'],
                            value=spec['value']
                        )
            self.success_count += 1
            self.products_created.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku
            })
            return True, None
        except Exception as e:
            error_msg = f"Row {row_num}: {str(e)}"
            self.errors.append(error_msg)
            self.failed_count += 1
            logger.error(error_msg)
            return False, error_msg
    
    def upload(self):
        try:
            df = self.read_excel_file()
            df = df.fillna('')
            if df.empty:
                raise ValidationError("Excel file is empty")
            for idx, row in df.iterrows():
                self.process_row(row, idx + 2)
            return {
                'success': True,
                'total_rows': len(df),
                'successful': self.success_count,
                'failed': self.failed_count,
                'errors': self.errors,
                'products_created': self.products_created
            }
        except ValidationError as e:
            return {
                'success': False,
                'message': str(e),
                'errors': self.errors
            }
        except Exception as e:
            error_msg = f"Unexpected error during upload: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'errors': self.errors + [error_msg]
            }
