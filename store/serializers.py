from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    Category,
    Brand,
    CustomerProfile,
    CustomerRequest,
    Inventory,
    OTPVerification,
    Product,
    ProductImage,
    ProductSpecification,
)


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "logo", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class CategoryReadSerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group", "subcategories"]

    def get_subcategories(self, obj):
        depth = self.context.get("depth", 0)
        max_depth = 3
        if depth >= max_depth:
            return []
        return CategoryReadSerializer(
            obj.subcategories.all(),
            many=True,
            context={"depth": depth + 1},
        ).data


class CategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = CategoryReadSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "navbar_group", "subcategories"]


class ProductSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source="brand.name")
    category_name = serializers.ReadOnlyField(source="category.name")
    subcategory_name = serializers.ReadOnlyField(source="subcategory.name")

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "category_name",
            "subcategory",
            "subcategory_name",
            "name",
            "brand",
            "brand_name",
            "mpn",
            "sku",
            "description",
            "highlights",
            "rating",
            "featured",
            "top_selling",
            "new_arrival",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "product", "image", "created_at"]
        read_only_fields = ["created_at"]


    def validate_image(self, value):
        max_size = 5 * 1024 * 1024
        content_type = getattr(value, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise serializers.ValidationError("Only image uploads are allowed.")
        if value.size > max_size:
            raise serializers.ValidationError("Image size must be 5MB or less.")
        return value


class ProductSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ["id", "product", "section", "key", "value"]

    def validate_section(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Section is required.")
        return value

    def validate_key(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Key is required.")
        return value

    def validate_value(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Value is required.")
        return value


class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = Inventory
        fields = ["id", "product", "product_name", "stock", "updated_at"]
        read_only_fields = ["updated_at"]


class CustomerRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerRequest
        fields = [
            "id",
            "product",
            "quantity",
            "name",
            "email",
            "phone",
            "description",
            "status",
            "created_at",
            "updated_at",
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


# class CustomerRegistrationSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, min_length=8)
#     username = serializers.CharField(required=False, allow_blank=True)
#     email = serializers.EmailField(required=True)

#     class Meta:
#         model = User
#         fields = ["username", "email", "password", "first_name", "last_name"]

#     def validate(self, attrs):
#         email = attrs["email"].strip().lower()
#         username = attrs.get("username", "").strip() or email

#         existing_user = User.objects.filter(email__iexact=email).first()
#         if existing_user and existing_user.is_active:
#             raise serializers.ValidationError({"email": "User with this email already exists."})

#         username_exists = User.objects.filter(username__iexact=username).first()
#         if username_exists:
#             # If the username exists and belongs to a DIFFERENT email, it's a conflict
#             if username_exists.email.lower() != email:
#                 raise serializers.ValidationError({"username": "This username is already taken."})
#             # If it's the same email but the user is active, it's already handled by the email check



#         attrs["email"] = email
#         attrs["username"] = username
#         validate_password(attrs["password"])
#         return attrs

#     def create(self, validated_data):
#         return User.objects.create_user(
#             username=validated_data["username"],
#             email=validated_data["email"],
#             password=validated_data["password"],
#             first_name=validated_data.get("first_name", "").strip(),
#             last_name=validated_data.get("last_name", "").strip(),
#             is_active=False,
#         )
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
    otp = serializers.CharField(min_length=6, max_length=6)


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
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value
