from django.urls import path
from .views import (
    AutocompleteAPIView, BrandAPIView, BrandDetailAPIView,
    BulkProductUploadAPIView, CategoryAPIView, CategoryDetailAPIView,
    ProductAPIView, ProductDetailAPIView, ProductImageDetailAPIView,
    ProductImageListAPIView, ProductListAPIView,
    ProductSpecificationDetailAPIView, ProductSpecificationListAPIView,
    ProductSpecificationBulkDeleteAPIView, ProductSpecificationSectionsAPIView,
    RecentlyViewedProductsAPIView,
    SearchFacetsAPIView, SimilarProductsAPIView, SubCategoryAPIView,
    SubCategoryDetailAPIView,
)


urlpatterns = [
    path("categories/", CategoryAPIView.as_view(), name="category-list-create"),
    path("categories/<int:pk>/", CategoryDetailAPIView.as_view(), name="category-detail"),
    path("categories/<int:pk>/subcategories/", SubCategoryAPIView.as_view(), name="subcategory-list-create"),
    path("categories/<int:pk>/subcategories/<int:subcategory_pk>/", SubCategoryDetailAPIView.as_view(), name="subcategory-detail"),

    path("brands/", BrandAPIView.as_view(), name="brand-list-create"),
    path("brands/<int:pk>/", BrandDetailAPIView.as_view(), name="brand-detail"),

    path("products/", ProductAPIView.as_view(), name="product-list-create"),
    path("products/<int:pk>/", ProductDetailAPIView.as_view(), name="product-detail"),
    path("products/search/", ProductListAPIView.as_view(), name="product-search"),
    path("products/autocomplete/", AutocompleteAPIView.as_view(), name="product-autocomplete"),
    path("products/facets/", SearchFacetsAPIView.as_view(), name="product-facets"),
    path("products/<int:product_id>/similar/", SimilarProductsAPIView.as_view(), name="similar-products"),
    path("products/bulk/upload/", BulkProductUploadAPIView.as_view(), name="bulk-product-upload"),
    path("products/recently-viewed/", RecentlyViewedProductsAPIView.as_view(), name="recently-viewed"),

    path("images/", ProductImageListAPIView.as_view(), name="image-list-create"),
    path("images/<int:pk>/", ProductImageDetailAPIView.as_view(), name="image-detail"),

    path("specifications/", ProductSpecificationListAPIView.as_view(), name="spec-list-create"),
    path("specifications/sections/", ProductSpecificationSectionsAPIView.as_view(), name="spec-sections"),
    path("specifications/bulk/delete/", ProductSpecificationBulkDeleteAPIView.as_view(), name="spec-bulk-delete"),
    path("specifications/<int:pk>/", ProductSpecificationDetailAPIView.as_view(), name="spec-detail"),
]