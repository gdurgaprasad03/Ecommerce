from django.urls import path
from .views import (
    CategoryAPIView, CategoryDetailAPIView, SubCategoryAPIView,
    BrandAPIView, BrandDetailAPIView, ProductAPIView, ProductDetailAPIView,
    ProductImageAPIView, ProductSpecificationAPIView, ProductListAPIView,
    SimilarProductsAPIView, BulkProductUploadAPIView
)

urlpatterns = [
    path("categories/", CategoryAPIView.as_view(), name="category-list-create"),
    path("categories/<int:pk>/", CategoryDetailAPIView.as_view(), name="category-detail"),
    path("categories/<int:pk>/subcategories/", SubCategoryAPIView.as_view(), name="subcategory-list-create"),
    path("brands/", BrandAPIView.as_view(), name="brand-list-create"),
    path("brands/<int:pk>/", BrandDetailAPIView.as_view(), name="brand-detail"),
    path("products/", ProductAPIView.as_view(), name="product-list-create"),
    path("products/<int:pk>/", ProductDetailAPIView.as_view(), name="product-detail"),
    path("products/search/", ProductListAPIView.as_view(), name="product-search"),
    path("products/<int:product_id>/similar/", SimilarProductsAPIView.as_view(), name="similar-products"),
    path("products/bulk/upload/", BulkProductUploadAPIView.as_view(), name="bulk-product-upload"),
    path("images/", ProductImageAPIView.as_view(), name="image-list-create"),
    path("images/<int:pk>/", ProductImageAPIView.as_view(), name="image-detail"),
    path("specifications/", ProductSpecificationAPIView.as_view(), name="spec-list-create"),
    path("specifications/<int:pk>/", ProductSpecificationAPIView.as_view(), name="spec-detail"),
]
