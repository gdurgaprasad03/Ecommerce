from rest_framework import serializers
from .models import Wishlist
from products.serializers import ProductSerializer
from products.models import Product

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
