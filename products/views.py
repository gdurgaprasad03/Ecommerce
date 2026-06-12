import logging

from django.db import IntegrityError, transaction
from django.db.models import Q, Prefetch, Avg
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination.views import PaginatedAPIView
from search.search import ElasticsearchSearchManager
from .cache_utils import cache_product_list, cache_product_detail
from .models import Brand, Category, Product, ProductImage, ProductSpecification
from .serializers import (
    BrandSerializer, CachedProductSerializer, CategoryReadSerializer,
    CategorySerializer, CategorySimpleSerializer, CategoryWriteSerializer,
    ProductImageSerializer, ProductListSerializer, ProductSerializer,
    ProductSpecificationSerializer,
)
from .services import BulkProductUploadService

logger = logging.getLogger(__name__)

SPEC_SECTIONS = [
    "Additional Details",
    "Audio / Ports",
    "Connectivity",
    "Display",
    "General",
    "Memory",
    "Operating System",
    "Physical",
    "Power",
    "Processor",
]


# ─────────────────────────────────────────────────────────────────────────────
# Shared queryset builder
#
# Optimisations applied:
#  1. inventory moved to select_related (JOIN) instead of prefetch_related
#     (separate query) — saves 1 DB round-trip per page load.
#  2. images, specifications, reviews prefetched in one query each instead of
#     one query per product (eliminates the N+1 problem).
#  3. related_products and frequently_bought_together prefetched with .only()
#     to avoid fetching unused columns.
#
# Result: product list page goes from ~81 queries to 5 queries regardless of
# how many products are on the page.
# ─────────────────────────────────────────────────────────────────────────────
def _build_product_queryset(include_inactive=False):
    from reviews.models import ProductReview

    qs = Product.objects.select_related(
        "brand",
        "category",
        "subcategory",
        "inventory",          # ← JOIN instead of separate query (was prefetch)
    ).prefetch_related(
        "images",             # ← 1 query for all images
        "specifications",     # ← 1 query for all specs
        Prefetch(
            "reviews",        # ← 1 query for all reviews
            queryset=ProductReview.objects.select_related("user").order_by("-created_at"),
        ),
        Prefetch(
            "related_products",
            queryset=Product.objects.filter(is_active=True).only(
                "id", "name", "product_image", "sku", "is_active"
            ),
            to_attr="active_related_products",
        ),
        Prefetch(
            "frequently_bought_together",
            queryset=Product.objects.filter(is_active=True).only(
                "id", "name", "product_image", "sku", "is_active"
            ),
            to_attr="active_fbt_products",
        ),
    )

    if not include_inactive:
        qs = qs.filter(is_active=True)

    return qs


def _build_product_list_queryset(include_inactive=False):
    """
    Lightweight queryset for list / grid endpoints. Same row filtering as
    _build_product_queryset, but WITHOUT the detail-only prefetches
    (reviews, specifications, related_products, frequently_bought_together).

    The list grid only needs scalar fields + brand/category joins + the image
    gallery, so we skip ~4 extra queries and the per-card relation loading on
    every page. Pairs with ProductListSerializer.
    """
    qs = Product.objects.select_related(
        "brand",
        "category",
        "subcategory",
        "inventory",          # JOIN — needed for price/stock on the card
    ).prefetch_related(
        "images",             # 1 query for all images on the page
    )

    if not include_inactive:
        qs = qs.filter(is_active=True)

    return qs


def _search_list_prefetch(qs):
    """
    Lightweight prefetch for the search results grid — joins + image gallery
    only, no detail-only relations. Pairs with ProductListSerializer.
    """
    return qs.select_related(
        "brand", "category", "subcategory", "inventory"
    ).prefetch_related(
        "images",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Brand
# ─────────────────────────────────────────────────────────────────────────────
class BrandAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Brand.objects.filter(is_active=True)
        return self.paginate(request, queryset, BrandSerializer)

    def post(self, request):
        serializer = BrandSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BrandDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        brand = get_object_or_404(Brand.objects.filter(is_active=True), pk=pk)
        return Response(BrandSerializer(brand, context={"request": request}).data)

    def put(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        serializer = BrandSerializer(
            brand, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        try:
            brand.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this brand because it is linked to existing products."},
                status=status.HTTP_409_CONFLICT,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Category
# ─────────────────────────────────────────────────────────────────────────────
class CategoryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        is_tree = request.query_params.get("tree", "false").lower() == "true"
        base_queryset = Category.objects.filter(is_active=True)
        queryset = base_queryset.filter(parent__isnull=True) if is_tree else base_queryset
        queryset = queryset.prefetch_related("subcategories")
        serializer_class = CategorySerializer if is_tree else CategorySimpleSerializer
        return self.paginate(request, queryset, serializer_class)

    def post(self, request):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": "A category with this name already exists at this level. Please choose a different name."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error creating category: {e}", exc_info=True)
            return Response(
                {"error": "Could not create the category. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(
            Category.objects.prefetch_related("subcategories").filter(is_active=True), pk=pk)
        return Response(CategorySerializer(category).data)

    def put(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": "A category with this name already exists at this level. Please choose a different name."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error updating category {pk}: {e}", exc_info=True)
            return Response(
                {"error": "Could not update the category. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(serializer.data)

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        try:
            category.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this category because it still has products or subcategories linked to it. "
                          "Remove or reassign them first, or mark the category as inactive instead."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error deleting category {pk}: {e}", exc_info=True)
            return Response(
                {"error": "Could not delete the category. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────────────────────
# SubCategory
# ─────────────────────────────────────────────────────────────────────────────
class SubCategoryAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(
            Category.objects.prefetch_related("subcategories").filter(is_active=True), pk=pk)
        serializer = CategoryReadSerializer(
            category.subcategories.filter(is_active=True), many=True, context={"depth": 0})
        return Response(serializer.data)

    def post(self, request, pk):
        parent_category = get_object_or_404(Category, pk=pk)
        data = request.data.copy()
        data["parent"] = parent_category.id
        serializer = CategoryWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": f'A subcategory with that name already exists under "{parent_category.name}". Please choose a different name.'},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error creating subcategory under category {pk}: {e}", exc_info=True)
            return Response(
                {"error": "Could not create the subcategory. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubCategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk, subcategory_pk):
        parent_category = get_object_or_404(
            Category.objects.prefetch_related("subcategories").filter(is_active=True), pk=pk)
        subcategory = get_object_or_404(
            parent_category.subcategories.filter(is_active=True), pk=subcategory_pk)
        return Response(CategoryReadSerializer(subcategory, context={"depth": 0}).data)

    def put(self, request, pk, subcategory_pk):
        parent_category = get_object_or_404(Category, pk=pk)
        subcategory = get_object_or_404(parent_category.subcategories.all(), pk=subcategory_pk)
        data = request.data.copy()
        data["parent"] = parent_category.id
        serializer = CategoryWriteSerializer(subcategory, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": f'A subcategory with that name already exists under "{parent_category.name}". Please choose a different name.'},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error updating subcategory {subcategory_pk} under category {pk}: {e}", exc_info=True)
            return Response(
                {"error": "Could not update the subcategory. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(CategoryReadSerializer(subcategory, context={"depth": 0}).data)

    def delete(self, request, pk, subcategory_pk):
        parent_category = get_object_or_404(Category, pk=pk)
        subcategory = get_object_or_404(parent_category.subcategories.all(), pk=subcategory_pk)
        try:
            subcategory.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": f'Cannot delete "{subcategory.name}" because it still has products linked to it. '
                          "Remove or reassign those products first, or mark the subcategory as inactive instead."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error deleting subcategory {subcategory_pk} under category {pk}: {e}", exc_info=True)
            return Response(
                {"error": "Could not delete the subcategory. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Product list + create
# ─────────────────────────────────────────────────────────────────────────────
class ProductAPIView(PaginatedAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    @cache_product_list(timeout=300)
    def get(self, request):
        include_inactive = (
            request.user.is_authenticated
            and request.user.is_staff
            and request.query_params.get("include_inactive", "").lower() == "true"
        )

        queryset = _build_product_list_queryset(include_inactive=include_inactive)

        if request.query_params.get("top_selling", "").lower() == "true":
            queryset = queryset.filter(top_selling=True)
        if request.query_params.get("featured", "").lower() == "true":
            queryset = queryset.filter(featured=True)
        if request.query_params.get("new_arrival", "").lower() == "true":
            queryset = queryset.filter(new_arrival=True)

        category_id = request.query_params.get("category")
        subcategory_id = request.query_params.get("subcategory")
        brand_param = request.query_params.get("brand")

        if category_id:
            try:
                cat_id_int = int(category_id)
                sub_ids = list(
                    Category.objects.filter(parent_id=cat_id_int)
                    .values_list("id", flat=True)
                )
                all_cat_ids = [cat_id_int] + sub_ids
                queryset = queryset.filter(
                    Q(category_id__in=all_cat_ids) |
                    Q(subcategory_id__in=sub_ids)
                )
            except (ValueError, TypeError):
                pass

        if subcategory_id:
            try:
                sub_id_int = int(subcategory_id)
                queryset = queryset.filter(
                    Q(subcategory_id=sub_id_int) |
                    Q(category_id=sub_id_int)
                )
            except (ValueError, TypeError):
                pass
        if brand_param:
            try:
                brand_id = int(str(brand_param).strip())
            except (TypeError, ValueError):
                brand_id = None

            if brand_id is not None:
                queryset = queryset.filter(brand_id=brand_id)
            else:
                queryset = queryset.filter(brand__name__iexact=str(brand_param).strip())

        response = self.paginate(request, queryset, ProductListSerializer)

        if request.user.is_authenticated and request.user.is_staff:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response

    def post(self, request):
        serializer = ProductSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        is_active = serializer.validated_data.get("is_active", True)
        serializer.save(is_active=is_active)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# Product detail
# ─────────────────────────────────────────────────────────────────────────────
class ProductDetailAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    @cache_product_detail(timeout=300)
    def get(self, request, pk):
        include_inactive = request.user.is_authenticated and request.user.is_staff
        queryset = _build_product_queryset(include_inactive=include_inactive)
        product = get_object_or_404(queryset, pk=pk)

        if request.user.is_authenticated:
            from .models import RecentlyViewedProduct
            RecentlyViewedProduct.objects.update_or_create(
                user=request.user, product=product)

        return Response(CachedProductSerializer(product, context={"request": request}).data)

    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(
            product, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product_id = product.id

        try:
            product.delete()
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this product permanently because it is linked to existing orders. "
                          "Please set it to Inactive instead."},
                status=status.HTTP_409_CONFLICT,
            )

        from core.cache_utils import CacheManager
        try:
            CacheManager.clear_product_cache(product_id)
            CacheManager.clear_product_list_cache()
            CacheManager.clear_analytics_cache()
            CacheManager.delete_cache(f"product_specs:{product_id}")
            CacheManager.delete_cache(f"product_reviews:{product_id}")
            CacheManager.delete_cache(f"product_inventory:{product_id}")
            logger.info(f"Explicit cache wipe after deleting product {product_id}")
        except Exception as e:
            logger.error(f"Explicit cache wipe FAILED after deleting product {product_id}: {e}", exc_info=True)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        response["Cache-Control"] = "no-store"
        return response


# ─────────────────────────────────────────────────────────────────────────────
# Product search (Elasticsearch + DB fallback)
# ─────────────────────────────────────────────────────────────────────────────
class ProductListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        search_query = request.query_params.get("search", "").strip()
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            page, page_size = 1, 20

        page_size = min(max(page_size, 1), 20)

        search_params = {
            "category_id": request.query_params.get("category"),
            "subcategory_id": request.query_params.get("subcategory"),
            "brand_id": request.query_params.get("brand"),
            "featured": request.query_params.get("featured", "").lower() == "true",
            "top_selling": request.query_params.get("top_selling", "").lower() == "true",
            "new_arrival": request.query_params.get("new_arrival", "").lower() == "true",
            "min_rating": request.query_params.get("min_rating"),
            "sort": request.query_params.get("sort", "-created_at"),
            "page": page,
            "page_size": page_size,
            "is_active": True,
        }

        search_result = None
        try:
            search_result = ElasticsearchSearchManager.search(search_query, **search_params)
        except Exception as e:
            logger.warning(f"Elasticsearch search failed, falling back to DB: {e}")

        if search_result:
            product_ids = search_result["ids"]
            preserved_order = {pid: pos for pos, pid in enumerate(product_ids)}
            queryset = _search_list_prefetch(Product.objects.filter(id__in=product_ids))
            products = sorted(queryset, key=lambda x: preserved_order.get(str(x.id), 0))
            serializer = ProductListSerializer(products, many=True, context={"request": request})
            return Response({
                "count": search_result["total"],
                "results": serializer.data,
                "took": search_result.get("took"),
                "page": page,
                "page_size": page_size,
            })

        queryset = _search_list_prefetch(Product.objects.filter(is_active=True))

        # ── Apply filters in DB fallback (same logic as ProductAPIView) ──────────
        fallback_category = request.query_params.get("category")
        if fallback_category:
            try:
                cat_id_int = int(fallback_category)
                sub_ids = list(
                    Category.objects.filter(parent_id=cat_id_int)
                    .values_list("id", flat=True)
                )
                all_cat_ids = [cat_id_int] + sub_ids
                queryset = queryset.filter(
                    Q(category_id__in=all_cat_ids) |
                    Q(subcategory_id__in=sub_ids)
                )
            except (ValueError, TypeError):
                pass

        fallback_subcategory = request.query_params.get("subcategory")
        if fallback_subcategory:
            try:
                sub_id_int = int(fallback_subcategory)
                queryset = queryset.filter(
                    Q(subcategory_id=sub_id_int) | Q(category_id=sub_id_int)
                )
            except (ValueError, TypeError):
                pass

        fallback_brand = request.query_params.get("brand")
        if fallback_brand:
            try:
                queryset = queryset.filter(brand_id=int(fallback_brand))
            except (ValueError, TypeError):
                queryset = queryset.filter(brand__name__iexact=fallback_brand)

        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(description__icontains=search_query)
            )
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        page_obj = paginator.paginate_queryset(queryset, request)
        serializer = ProductListSerializer(page_obj, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Recently Viewed
# ─────────────────────────────────────────────────────────────────────────────
class RecentlyViewedProductsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import RecentlyViewedProduct
        history = RecentlyViewedProduct.objects.filter(
            user=request.user,
            product__is_active=True,
        ).select_related(
            "product", "product__brand", "product__category",
            "product__inventory",
        ).prefetch_related(
            "product__images",
            "product__specifications",
        )[:10]
        products = [h.product for h in history]
        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Search helpers
# ─────────────────────────────────────────────────────────────────────────────
class AutocompleteAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        prefix = request.query_params.get("prefix", "")
        try:
            suggestions = ElasticsearchSearchManager.autocomplete(prefix)
        except Exception as e:
            logger.warning(f"Autocomplete failed: {e}")
            suggestions = []
        return Response({"suggestions": suggestions})


class SearchFacetsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            facets = ElasticsearchSearchManager.get_facets()
        except Exception as e:
            logger.warning(f"Facets failed: {e}")
            facets = {}
        return Response(facets)


class SimilarProductsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id, is_active=True)
        try:
            limit = int(request.query_params.get("limit", 5))
        except (TypeError, ValueError):
            limit = 5
        limit = max(1, min(limit, 20))
        similar = (
            Product.objects.filter(category=product.category, is_active=True)
            .exclude(pk=product_id)
            .select_related("brand", "category", "inventory")
            .prefetch_related("images")
            .order_by("-rating")[:limit]
        )
        return Response({
            "current_product": ProductSerializer(product).data,
            "similar_products": ProductSerializer(similar, many=True).data,
            "count": len(similar),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Product Images
# ─────────────────────────────────────────────────────────────────────────────
class ProductImageListAPIView(PaginatedAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = ProductImage.objects.select_related("product").all()
        product_id = request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return self.paginate(request, queryset, ProductImageSerializer)

    def post(self, request):
        serializer = ProductImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductImageDetailAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        image_obj = get_object_or_404(ProductImage.objects.select_related("product"), pk=pk)
        return Response(ProductImageSerializer(image_obj, context={"request": request}).data)

    def put(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        serializer = ProductImageSerializer(
            image_obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        image_obj = get_object_or_404(ProductImage.objects.select_related("product"), pk=pk)
        product_id = image_obj.product_id
        product_name = image_obj.product.name
        image_obj.delete()
        try:
            from core.cache_utils import CacheManager
            CacheManager.delete_cache(f"product:{product_id}:public")
            CacheManager.delete_cache(f"product_images:{product_id}")
            CacheManager.clear_product_list_cache()
        except Exception as e:
            logger.error(f"Cache clear failed after image delete: {e}", exc_info=True)
        return Response(
            {"message": f"Image removed from {product_name} successfully."},
            status=status.HTTP_200_OK,
        )


class ProductImageDeleteAPIView(APIView):
    """DELETE /products/products/{product_id}/images/{image_id}/"""
    permission_classes = [IsAdminUser]

    def delete(self, request, product_id, image_id):
        product = get_object_or_404(Product, pk=product_id)
        image_obj = get_object_or_404(ProductImage, pk=image_id, product=product)
        image_obj.delete()
        try:
            from core.cache_utils import CacheManager
            CacheManager.delete_cache(f"product:{product_id}:public")
            CacheManager.delete_cache(f"product_images:{product_id}")
            CacheManager.clear_product_list_cache()
        except Exception as e:
            logger.error(f"Cache clear failed after image delete: {e}", exc_info=True)
        return Response(
            {"message": f"Image deleted from {product.name} successfully."},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Product Specifications
# ─────────────────────────────────────────────────────────────────────────────
class ProductSpecificationListAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = ProductSpecification.objects.select_related("product").order_by(
            "product_id", "section", "key", "id")
        product_id = request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if request.query_params.get("grouped", "").lower() == "true":
            specs = list(queryset)
            grouped = {}
            for spec in specs:
                grouped.setdefault(spec.section, []).append(
                    ProductSpecificationSerializer(spec).data)
            all_sections = list(grouped.keys())
            for s in SPEC_SECTIONS:
                if s not in all_sections:
                    all_sections.append(s)
            return Response([{"section": s, "specs": grouped.get(s, [])} for s in all_sections])

        return self.paginate(request, queryset, ProductSpecificationSerializer)

    def post(self, request):
        data = request.data
        if isinstance(data, list):
            return self._bulk_create(data)
        serializer = ProductSpecificationSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": f"A specification with key \"{data.get('key')}\" already exists "
                          f"in section \"{data.get('section')}\" for this product. Use PUT to update it instead."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _bulk_create(self, data_list):
        if not isinstance(data_list, list) or len(data_list) == 0:
            return Response(
                {"error": "Provide a non-empty list of specification objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created_specs, updated_specs, errors = [], [], []
        try:
            with transaction.atomic():
                for idx, item in enumerate(data_list):
                    serializer = ProductSpecificationSerializer(data=item)
                    if not serializer.is_valid():
                        errors.append({"index": idx, "errors": serializer.errors})
                        continue
                    spec, created = ProductSpecification.objects.update_or_create(
                        product=serializer.validated_data["product"],
                        section=serializer.validated_data["section"],
                        key=serializer.validated_data["key"],
                        defaults={"value": serializer.validated_data["value"]},
                    )
                    (created_specs if created else updated_specs).append(
                        ProductSpecificationSerializer(spec).data)
        except Exception as e:
            logger.error(f"Error in bulk specification save: {e}", exc_info=True)
            return Response(
                {"error": "Failed to save specifications. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response_data = {
            "created": len(created_specs),
            "updated": len(updated_specs),
            "specs": created_specs + updated_specs,
        }
        if errors:
            response_data["validation_errors"] = errors
            return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
        return Response(response_data, status=status.HTTP_201_CREATED)


class ProductSpecificationDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        spec = get_object_or_404(ProductSpecification.objects.select_related("product"), pk=pk)
        return Response(ProductSpecificationSerializer(spec).data)

    def put(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        serializer = ProductSpecificationSerializer(spec, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except IntegrityError:
            return Response(
                {"error": "A specification with that key already exists in this section. Please use a different key name."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(serializer.data)

    def delete(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        section, key = spec.section, spec.key
        spec.delete()
        return Response(
            {"message": f"Specification \"{key}\" removed from section \"{section}\"."},
            status=status.HTTP_200_OK,
        )


class ProductSpecificationBulkDeleteAPIView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request):
        ids = request.data.get("ids", [])
        if not ids or not isinstance(ids, list):
            return Response(
                {"error": "Provide a non-empty list of spec IDs to delete."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted_count, _ = ProductSpecification.objects.filter(pk__in=ids).delete()
        return Response(
            {"message": f"{deleted_count} specification(s) deleted successfully."},
            status=status.HTTP_200_OK,
        )


class ProductSpecificationSectionsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"sections": SPEC_SECTIONS})


# ─────────────────────────────────────────────────────────────────────────────
# Bulk Product Upload
# ─────────────────────────────────────────────────────────────────────────────
class BulkProductUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAdminUser]

    def post(self, request):
        if "excel_file" not in request.FILES:
            return Response(
                {"error": "No Excel file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        excel_file = request.FILES["excel_file"]
        uploaded_images = {f.name: f for f in request.FILES.getlist("images")}
        try:
            service = BulkProductUploadService(excel_file, uploaded_images)
            result = service.upload()
            if not result["success"]:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            has_issues = bool(result.get("warnings")) or result.get("failed", 0) > 0
            if has_issues and result.get("successful", 0) > 0:
                return Response(result, status=status.HTTP_207_MULTI_STATUS)
            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Bulk upload error: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)