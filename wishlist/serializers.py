import logging
from rest_framework import serializers
from .models import Wishlist
from products.serializers import ProductSerializer
from products.models import Product

logger = logging.getLogger(__name__)

class WishlistSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)
    product_ids = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        required=False,
        allow_empty=True,
        many=True,
        source="products"
    )

    class Meta:
        model = Wishlist
        fields = ["id", "user", "products", "product_ids", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "products", "created_at", "updated_at"]

    def validate_product_ids(self, value):
        try:
            if value and not isinstance(value, list):
                raise serializers.ValidationError("product_ids must be a list.")
            return value
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating product_ids: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Invalid product_ids value.")

