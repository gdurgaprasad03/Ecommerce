from django.contrib import admin
from .models import (
    Category,
    Brand,
    Product,
    Inventory,
    CustomerRequest,
    ProductImage,
    ProductSpecification,
    OTPVerification,
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active", "created_at")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "parent")
    search_fields = ("name",)
    list_filter = ("parent",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "brand",
        "category",
        "featured",
        "top_selling",
        "new_arrival",
        "created_at",
    )
    list_filter = ("category", "featured", "top_selling", "new_arrival", "created_at")
    search_fields = ("name", "brand__name", "description", "highlights")


    inlines = [ProductImageInline, ProductSpecificationInline]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "created_at")
    search_fields = ("product__name",)
    list_filter = ("created_at",)


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "section", "key", "value")
    search_fields = ("product__name", "section", "key", "value")
    list_filter = ("section",)



@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "stock", "updated_at")
    search_fields = ("product__name",)
    list_filter = ("updated_at",)


@admin.register(CustomerRequest)
class CustomerRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "email",
        "phone",
        "product",
        "quantity",
        "status",
        "stock_deducted",
        "created_at",
    )
    search_fields = ("name", "email", "phone", "product__name")
    list_filter = ("status", "stock_deducted", "created_at")
    readonly_fields = ("stock_deducted", "created_at", "updated_at")


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "otp", "is_verified", "verified_at", "attempts", "expires_at", "last_sent_at", "created_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("expires_at", "created_at")
