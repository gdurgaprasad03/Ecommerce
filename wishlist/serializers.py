import logging
from rest_framework import serializers
from .models import Wishlist
from products.serializers import ProductSerializer
from products.models import Product

logger = logging.getLogger(__name__)


class WishlistSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for returning a wishlist with full product detail.

    FIX: Removed 'product_ids' write field that shared source="products" with
    the 'products' read field. In DRF >=3.15 two fields targeting the same
    source ("products") in the same serializer causes field-binding conflicts
    that surface as AssertionErrors or bad attribute access during serialization.
    Write operations (add / remove) are handled directly in the view using the
    M2M manager, so a write path in this serializer was never needed.
    """
    products = ProductSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = ["id", "user", "products", "product_count", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def get_product_count(self, obj):
        try:
            return obj.products.count()
        except Exception as e:
            logger.warning(f"Could not compute product_count for wishlist {obj.id}: {e}")
            return 0