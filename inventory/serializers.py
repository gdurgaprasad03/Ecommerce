import logging
from rest_framework import serializers
from core.utils.serializers import SanitizedModelSerializer
from .models import Inventory
from products.models import Product

logger = logging.getLogger(__name__)

class InventorySerializer(SanitizedModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = Inventory
        fields = ["id", "product", "product_name", "stock", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_stock(self, value):
        try:
            if value < 0:
                raise serializers.ValidationError("Stock cannot be negative.")
            return value
        except Exception as e:
            logger.error(f"Error validating stock: {str(e)}")
            raise serializers.ValidationError("Invalid stock value.")

