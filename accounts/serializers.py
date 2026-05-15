import logging
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password as django_validate_password
from rest_framework import serializers
import re
from core.utils.serializers import SanitizedModelSerializer
from .validators import validate_password_complexity

logger = logging.getLogger(__name__)

class CustomerRegistrationSerializer(SanitizedModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    confirm_password = serializers.CharField(write_only=True, required=True)
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=True)
    company_name = serializers.CharField(required=True, max_length=255)
    company_address = serializers.CharField(required=True, max_length=1000)
    phone = serializers.CharField(required=False, max_length=20)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "company_name",
            "company_address",
            "phone",
        ]

    def validate_email(self, value):
        try:
            value = value.strip().lower()
            disposable_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com', 'mailinator.com']
            domain = value.split('@')[1].lower() if '@' in value else ""
            if domain in disposable_domains:
                raise serializers.ValidationError("Disposable email addresses are not allowed")

            if User.objects.filter(email__iexact=value).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError("User with this email already exists")

            return value
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating email: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Invalid email format.")

    def validate_password(self, value):
        try:
            validate_password_complexity(value)
            django_validate_password(value)
        except Exception as e:
            if hasattr(e, 'messages'):
                raise serializers.ValidationError(e.messages)
            raise serializers.ValidationError(str(e))
        return value

    def validate_company_name(self, value):
        try:
            return value.strip()
        except Exception as e:
            logger.error(f"Error validating company name: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Invalid company name.")

    def validate_company_address(self, value):
        try:
            return value.strip()
        except Exception as e:
            logger.error(f"Error validating company address: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Invalid company address.")

    def validate(self, attrs):
        try:
            email = attrs["email"].strip().lower()
            username = attrs.get("username", "").strip() or email
            password = attrs.get("password")
            confirm_password = attrs.get("confirm_password")

            if password != confirm_password:
                raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and existing_user.is_active:
                raise serializers.ValidationError({"email": "User with this email already exists."})

            username_exists = User.objects.filter(username__iexact=username).exclude(email__iexact=email).first()
            if username_exists:
                raise serializers.ValidationError({"username": "This username is already taken."})

            attrs["email"] = email
            attrs["username"] = username
            attrs["company_name"] = attrs["company_name"].strip()
            attrs["company_address"] = attrs["company_address"].strip()

            attrs.pop("confirm_password", None)

            return attrs
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating registration data: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Error validating registration data.")

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6, required=False, allow_blank=True)
    code = serializers.CharField(min_length=6, max_length=6, required=False, allow_blank=True)

    def validate(self, attrs):
        try:
            otp = attrs.get("otp") or attrs.get("code")
            if not otp:
                raise serializers.ValidationError({"otp": "OTP is required."})

            if not otp.isdigit():
                raise serializers.ValidationError({"otp": "OTP must contain only digits."})

            attrs["otp"] = otp
            return attrs
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating OTP: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Error validating OTP.")

class OTPResendSerializer(serializers.Serializer):
    email = serializers.EmailField()

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs):
        try:
            login_id = (attrs.get("username") or attrs.get("email") or "").strip()
            password = attrs.get("password", "").strip()

            if not login_id or not password:
                raise serializers.ValidationError("Username/email and password are required.")

            attrs["login_id"] = login_id
            attrs["password"] = password
            return attrs
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating login data: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Error validating login data.")

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, required=False, allow_blank=True)
    code = serializers.CharField(max_length=6, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        try:
            otp = attrs.get("otp") or attrs.get("code")
            if not otp:
                raise serializers.ValidationError({"otp": "OTP is required."})

            if not otp.isdigit():
                raise serializers.ValidationError({"otp": "OTP must contain only digits."})

            if attrs.get("new_password") != attrs.get("confirm_password"):
                raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

            attrs["otp"] = otp
            return attrs
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating password reset data: {str(e)}", exc_info=True)
            raise serializers.ValidationError("Error validating password reset data.")

    def validate_new_password(self, value):
        try:
            validate_password_complexity(value)
            django_validate_password(value)
        except Exception as e:
            if hasattr(e, 'messages'):
                raise serializers.ValidationError(e.messages)
            raise serializers.ValidationError(str(e))
        return value
