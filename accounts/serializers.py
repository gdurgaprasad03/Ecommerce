from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.html import escape
from rest_framework import serializers
import re

class CustomerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12, max_length=128)
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
            "first_name",
            "last_name",
            "company_name",
            "company_address",
            "phone",
        ]

    def validate_email(self, value):
        """Validate email and prevent disposable emails"""
        value = value.strip().lower()
        disposable_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com', 'mailinator.com']
        domain = value.split('@')[1].lower() if '@' in value else ""
        if domain in disposable_domains:
            raise serializers.ValidationError("Disposable email addresses are not allowed")
        
        # Check if email already exists (case-insensitive)
        if User.objects.filter(email__iexact=value).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError("User with this email already exists")
        
        return value

    def validate_password(self, value):
        """Validate password complexity"""
        if len(value) < 12:
            raise serializers.ValidationError("Password must be at least 12 characters")
        if not any(c.isupper() for c in value):
            raise serializers.ValidationError("Password must contain uppercase letters")
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain numbers")
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in value):
            raise serializers.ValidationError("Password must contain special characters")
        
        validate_password(value)
        return value

    def validate_company_name(self, value):
        """Sanitize company name"""
        return escape(value.strip())

    def validate_company_address(self, value):
        """Sanitize company address"""
        return escape(value.strip())

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        username = attrs.get("username", "").strip() or email

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

        return attrs


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6, required=False, allow_blank=True)
    code = serializers.CharField(min_length=6, max_length=6, required=False, allow_blank=True)

    def validate(self, attrs):
        otp = attrs.get("otp") or attrs.get("code")
        if not otp:
            raise serializers.ValidationError({"otp": "OTP is required."})
        
        # Validate OTP format (should be digits only)
        if not otp.isdigit():
            raise serializers.ValidationError({"otp": "OTP must contain only digits."})
        
        attrs["otp"] = otp
        return attrs


class OTPResendSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, max_length=128)

    def validate(self, attrs):
        login_id = (attrs.get("username") or attrs.get("email") or "").strip()
        password = attrs.get("password", "").strip()
        
        if not login_id or not password:
            raise serializers.ValidationError("Username/email and password are required.")
        
        attrs["login_id"] = login_id
        attrs["password"] = password
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, required=False, allow_blank=True)
    code = serializers.CharField(max_length=6, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, min_length=12, max_length=128)

    def validate(self, attrs):
        otp = attrs.get("otp") or attrs.get("code")
        if not otp:
            raise serializers.ValidationError({"otp": "OTP is required."})
        
        if not otp.isdigit():
            raise serializers.ValidationError({"otp": "OTP must contain only digits."})
        
        attrs["otp"] = otp
        return attrs

    def validate_new_password(self, value):
        """Validate new password complexity"""
        if len(value) < 12:
            raise serializers.ValidationError("Password must be at least 12 characters")
        if not any(c.isupper() for c in value):
            raise serializers.ValidationError("Password must contain uppercase letters")
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain numbers")
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in value):
            raise serializers.ValidationError("Password must contain special characters")
        
        validate_password(value)
        return value
