from rest_framework import serializers
from core.utils.serializers import SanitizedModelSerializer
from .models import Inventory
from products.models import Product

class InventorySerializer(SanitizedModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = Inventory
        fields = ["id", "product", "product_name", "stock", "updated_at"]
        read_only_fields = ["updated_at"]
