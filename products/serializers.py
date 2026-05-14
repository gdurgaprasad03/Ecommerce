from django.conf import settings
from django.utils.http import urlencode
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from core.utils.serializers import SanitizedModelSerializer, validate_image_file
from .models import Brand, Category, Product, ProductImage, ProductSpecification


class BrandSerializer(SanitizedModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "logo", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_logo(self, value):
        return validate_image_file(value)


class CategoryReadSerializer(SanitizedModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group", "subcategories"]

    def get_subcategories(self, obj):
        depth = self.context.get("depth", 0)
        max_depth = 3
        if depth >= max_depth:
            return []
        return CategoryReadSerializer(
            obj.subcategories.all(),
            many=True,
            context={"depth": depth + 1},
        ).data


class CategoryWriteSerializer(SanitizedModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = CategoryReadSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group", "is_active", "subcategories"]


class CategorySimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group", "is_active"]


class ProductMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "product_image", "sku", "is_active"]


class ProductSerializer(SanitizedModelSerializer):
    brand_name = serializers.ReadOnlyField(source="brand.name")
    category_name = serializers.ReadOnlyField(source="category.name")
    subcategory_name = serializers.ReadOnlyField(source="subcategory.name")

    class Meta:
        model = Product
        fields = [
            "id", "category", "category_name", "subcategory", "subcategory_name",
            "name", "product_image", "brand", "brand_name", "mpn", "sku",
            "description", "highlights", "rating", "featured", "top_selling",
            "new_arrival", "is_active", "related_products", "frequently_bought_together", "created_at", "updated_at",
        ]
        # is_active is now writable. Public read access is filtered at the view layer.
        read_only_fields = [
            "id", "category_name", "subcategory_name", "brand_name",
            "created_at", "updated_at",
        ]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Use prefetched related products if available to avoid extra DB queries
        if "related_products" in representation:
            # We filter in-memory if already prefetched, or fallback to DB if not
            related_products = getattr(instance, "active_related_products", None)
            if related_products is None:
                related_products = instance.related_products.filter(is_active=True)
            representation["related_products"] = ProductMinimalSerializer(related_products, many=True).data
        
        if "frequently_bought_together" in representation:
            fbt_products = getattr(instance, "active_fbt_products", None)
            if fbt_products is None:
                fbt_products = instance.frequently_bought_together.filter(is_active=True)
            representation["frequently_bought_together"] = ProductMinimalSerializer(fbt_products, many=True).data
        
        # WhatsApp Share Link
        frontend_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
        product_url = f"{frontend_url}/products/{instance.id}"
        message = f"Hey, check out this {instance.name} on our site! {product_url}"
        representation["whatsapp_share_link"] = f"https://wa.me/?text={urlencode({'': message})[1:]}"
        
        # SEO Meta Tags
        representation["meta_title"] = f"{instance.name} | Buy {instance.category.name if instance.category else 'Products'} Online"
        desc = instance.description or ""
        representation["meta_description"] = (desc[:157] + "...") if len(desc) > 160 else desc
        
        return representation

    def validate_product_image(self, value):
        return validate_image_file(value)

    def validate_sku(self, value):
        if value:
            value = value.strip()
            if value == "":
                return None
        return value or None

    def to_internal_value(self, data):
        data = data.copy()
        for field in ["category", "subcategory", "brand"]:
            if field in data and isinstance(data[field], dict) and "id" in data[field]:
                data[field] = data[field]["id"]
            val = data.get("product_image")
            if isinstance(val, str):
                data.pop("product_image")
        
        return super().to_internal_value(data)


class ProductImageSerializer(SanitizedModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "product", "image", "image_url", "created_at"]
        read_only_fields = ["created_at", "image_url"]

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def validate_image(self, value):
        return validate_image_file(value)


class ProductSpecificationSerializer(SanitizedModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ["id", "product", "section", "key", "value"]
        validators = [
            UniqueTogetherValidator(
                queryset=ProductSpecification.objects.all(),
                fields=["product", "section", "key"],
                message="This specification key already exists for this section of the product.",
            )
        ]

    def validate_section(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Section is required.")
        return value

    def validate_key(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Key is required.")
        return value

    def validate_value(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Value is required.")
        return value


class CachedProductSerializer(ProductSerializer):
    images = serializers.SerializerMethodField()
    specifications = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ["images", "specifications", "reviews", "inventory"]

    def get_images(self, obj):
        from core.cache_utils import CacheManager
        cache_key = f"product_images:{obj.id}"
        images = CacheManager.get_cache(cache_key)
        if images is None:
            images = ProductImageSerializer(obj.images.all(), many=True).data
            CacheManager.set_cache(cache_key, images, timeout=3600)
        return images

    def get_specifications(self, obj):
        from core.cache_utils import CacheManager
        cache_key = f"product_specs:{obj.id}"
        specs = CacheManager.get_cache(cache_key)
        if specs is None:
            specs = ProductSpecificationSerializer(obj.specifications.all(), many=True).data
            CacheManager.set_cache(cache_key, specs, timeout=3600)
        return specs

    def get_reviews(self, obj):
        from core.cache_utils import CacheManager
        from reviews.serializers import ProductReviewSerializer
        cache_key = f"product_reviews:{obj.id}"
        reviews = CacheManager.get_cache(cache_key)
        if reviews is None:
            reviews = ProductReviewSerializer(obj.reviews.all()[:5], many=True).data
            CacheManager.set_cache(cache_key, reviews, timeout=1800)
        return reviews

    def get_inventory(self, obj):
        from core.cache_utils import CacheManager
        from inventory.serializers import InventorySerializer
        cache_key = f"product_inventory:{obj.id}"
        inventory = CacheManager.get_cache(cache_key)
        if inventory is None:
            try:
                inventory = InventorySerializer(obj.inventory).data
                CacheManager.set_cache(cache_key, inventory, timeout=600)
            except Exception:
                inventory = None
        return inventory


class CachedCategorySerializer(CategoryReadSerializer):
    def to_representation(self, instance):
        from core.cache_utils import CacheManager
        cache_key = f"category_detail:{instance.id}"
        cached_data = CacheManager.get_cache(cache_key)
        if cached_data is not None:
            return cached_data
        data = super().to_representation(instance)
        CacheManager.set_cache(cache_key, data, timeout=7200)
        return data


class CachedBrandSerializer(BrandSerializer):
    def to_representation(self, instance):
        from core.cache_utils import CacheManager
        cache_key = f"brand_detail:{instance.id}"
        cached_data = CacheManager.get_cache(cache_key)
        if cached_data is not None:
            return cached_data
        data = super().to_representation(instance)
        CacheManager.set_cache(cache_key, data, timeout=7200)
        return data