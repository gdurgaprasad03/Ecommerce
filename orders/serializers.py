import logging
from rest_framework import serializers
from core.utils.serializers import SanitizedModelSerializer
from .models import CustomerRequest, Enquiry

logger = logging.getLogger(__name__)

class CustomerRequestSerializer(SanitizedModelSerializer):
    class Meta:
        model = CustomerRequest
        fields = [
            "id", "product", "quantity", "name", "email", "phone",
            "description", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at"]

    def validate_phone(self, value):
        try:
            normalized = "".join(ch for ch in value if ch.isdigit())
            if len(normalized) < 10 or len(normalized) > 15:
                raise serializers.ValidationError("Enter a valid phone number.")
            return normalized
        except Exception as e:
            logger.error(f"Error validating phone number: {str(e)}")
            raise serializers.ValidationError("Invalid phone number format.")

class CustomerRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerRequest
        fields = ["status"]

    def validate_status(self, value):
        try:
            valid = {choice[0] for choice in CustomerRequest.STATUS_CHOICES}
            if value not in valid:
                raise serializers.ValidationError("Invalid status value.")
            return value
        except Exception as e:
            logger.error(f"Error validating status: {str(e)}")
            raise serializers.ValidationError("Invalid status.")

class EnquirySerializer(SanitizedModelSerializer):
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
        try:
            value = value.strip()
            if not value:
                raise serializers.ValidationError("Name is required.")
            return value
        except Exception as e:
            logger.error(f"Error validating name: {str(e)}")
            raise serializers.ValidationError("Invalid name.")

    def validate_phone(self, value):
        try:
            normalized = "".join(ch for ch in value if ch.isdigit())
            if len(normalized) < 10 or len(normalized) > 15:
                raise serializers.ValidationError("Enter a valid phone number.")
            return normalized
        except Exception as e:
            logger.error(f"Error validating phone number: {str(e)}")
            raise serializers.ValidationError("Invalid phone number format.")

    def validate_company_name(self, value):
        try:
            value = value.strip()
            if not value:
                raise serializers.ValidationError("Company name is required.")
            return value
        except Exception as e:
            logger.error(f"Error validating company name: {str(e)}")
            raise serializers.ValidationError("Invalid company name.")

    def validate_company_address(self, value):
        try:
            value = value.strip()
            if not value:
                raise serializers.ValidationError("Company address is required.")
            return value
        except Exception as e:
            logger.error(f"Error validating company address: {str(e)}")
            raise serializers.ValidationError("Invalid company address.")
