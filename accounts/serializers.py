from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

class CustomerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    company_name = serializers.CharField(required=True, max_length=255)
    company_address = serializers.CharField(required=True)

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
        ]

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        username = attrs.get("username", "").strip() or email

        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user and existing_user.is_active:
            raise serializers.ValidationError({"email": "User with this email already exists."})

        username_exists = User.objects.filter(username__iexact=username).first()
        if username_exists and username_exists.email.lower() != email:
            raise serializers.ValidationError({"username": "This username is already taken."})

        attrs["email"] = email
        attrs["username"] = username
        attrs["company_name"] = attrs["company_name"].strip()
        attrs["company_address"] = attrs["company_address"].strip()

        validate_password(attrs["password"])
        return attrs


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6, required=False, allow_blank=True)
    code = serializers.CharField(min_length=6, max_length=6, required=False, allow_blank=True)

    def validate(self, attrs):
        otp = attrs.get("otp") or attrs.get("code")
        if not otp:
            raise serializers.ValidationError({"otp": "OTP is required."})
        attrs["otp"] = otp
        return attrs


class OTPResendSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login_id = attrs.get("username") or attrs.get("email")
        if not login_id or not attrs.get("password"):
            raise serializers.ValidationError("Username/email and password are required.")
        attrs["login_id"] = login_id.strip()
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, required=False, allow_blank=True)
    code = serializers.CharField(max_length=6, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        otp = attrs.get("otp") or attrs.get("code")
        if not otp:
            raise serializers.ValidationError({"otp": "OTP is required."})
        attrs["otp"] = otp
        return attrs

    def validate_new_password(self, value):
        validate_password(value)
        return value
