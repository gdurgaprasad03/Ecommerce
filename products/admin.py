from django.contrib import admin
from .models import Category, Brand, Product, ProductImage, ProductSpecification

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
    list_display = ("id", "name", "brand", "category", "featured", "top_selling", "new_arrival", "created_at")
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
