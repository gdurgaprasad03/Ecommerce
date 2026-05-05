from rest_framework import serializers
from core.utils.serializers import SanitizedModelSerializer
from .models import ProductReview

class ProductReviewSerializer(SanitizedModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", read_only=True)

    class Meta:
        model = ProductReview
        fields = ["id", "product", "user_id", "username", "rating", "title", "comment", "helpful_count", "is_verified", "created_at", "updated_at"]
        read_only_fields = ["id", "helpful_count", "is_verified", "created_at", "updated_at"]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
