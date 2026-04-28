from rest_framework import serializers
from .models import CustomerRequest, Enquiry

class CustomerRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerRequest
        fields = [
            "id", "product", "quantity", "name", "email", "phone",
            "description", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at"]

    def validate_phone(self, value):
        normalized = "".join(ch for ch in value if ch.isdigit())
        if len(normalized) < 10 or len(normalized) > 15:
            raise serializers.ValidationError("Enter a valid phone number.")
        return normalized

class CustomerRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerRequest
        fields = ["status"]

    def validate_status(self, value):
        valid = {choice[0] for choice in CustomerRequest.STATUS_CHOICES}
        if value not in valid:
            raise serializers.ValidationError("Invalid status value.")
        return value

class EnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = [
            "id", "name", "company_name", "company_address", "product",
            "quantity", "phone", "email", "description", "created_at",
        ]
        read_only_fields = ["created_at"]
        extra_kwargs = {
            "name": {"required": True, "allow_blank": False},
            "company_name": {"required": True, "allow_blank": False},
            "company_address": {"required": True, "allow_blank": False},
            "quantity": {"required": True},
            "phone": {"required": True, "allow_blank": False},
            "email": {"required": True, "allow_blank": False},
            "product": {"required": False, "allow_null": True},
            "description": {"required": False, "allow_blank": True},
        }

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_phone(self, value):
        normalized = "".join(ch for ch in value if ch.isdigit())
        if len(normalized) < 10 or len(normalized) > 15:
            raise serializers.ValidationError("Enter a valid phone number.")
        return normalized

    def validate_company_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Company name is required.")
        return value

    def validate_company_address(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Company address is required.")
        return value
