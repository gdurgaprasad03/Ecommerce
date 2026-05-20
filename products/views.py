import logging

from django.db.models import Q, Prefetch, Avg
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
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
    ProductImageSerializer, ProductSerializer, ProductSpecificationSerializer,
)
from .services import BulkProductUploadService

logger = logging.getLogger(__name__)



class BrandAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Brand.objects.filter(is_active=True)
        return self.paginate(request, queryset, BrandSerializer)

    def post(self, request):
        serializer = BrandSerializer(
            data=request.data, context={"request": request})
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
            brand, data=request.data, partial=True, context={"request": request}
        )
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



class CategoryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        is_tree = request.query_params.get("tree", "false").lower() == "true"
        base_queryset = Category.objects.filter(is_active=True)
        queryset = base_queryset.filter(
            parent__isnull=True) if is_tree else base_queryset
        queryset = queryset.prefetch_related("subcategories")
        serializer_class = CategorySerializer if is_tree else CategorySimpleSerializer
        return self.paginate(request, queryset, serializer_class)

    def post(self, request):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(
            Category.objects.prefetch_related(
                "subcategories").filter(is_active=True),
            pk=pk,
        )
        return Response(CategorySerializer(category).data)

    def put(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategoryWriteSerializer(
            category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        try:
            category.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this category because it is linked to existing products or subcategories."},
                status=status.HTTP_409_CONFLICT,
            )


class SubCategoryAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(
            Category.objects.prefetch_related(
                "subcategories").filter(is_active=True),
            pk=pk,
        )
        serializer = CategoryReadSerializer(
            category.subcategories.filter(is_active=True),
            many=True,
            context={"depth": 0},
        )
        return Response(serializer.data)

    def post(self, request, pk):
        parent_category = get_object_or_404(Category, pk=pk)
        data = request.data.copy()
        data["parent"] = parent_category.id
        serializer = CategoryWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubCategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk, subcategory_pk):
        parent_category = get_object_or_404(
            Category.objects.prefetch_related("subcategories").filter(is_active=True),
            pk=pk,
        )
        subcategory = get_object_or_404(
            parent_category.subcategories.filter(is_active=True),
            pk=subcategory_pk,
        )
        return Response(CategoryReadSerializer(subcategory, context={"depth": 0}).data)

    def put(self, request, pk, subcategory_pk):
        parent_category = get_object_or_404(Category, pk=pk)
        subcategory = get_object_or_404(
            parent_category.subcategories.all(),
            pk=subcategory_pk,
        )
        data = request.data.copy()
        data["parent"] = parent_category.id
        serializer = CategoryWriteSerializer(
            subcategory, data=data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk, subcategory_pk):
        parent_category = get_object_or_404(Category, pk=pk)
        subcategory = get_object_or_404(
            parent_category.subcategories.all(),
            pk=subcategory_pk,
        )
        try:
            subcategory.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this subcategory because it is linked to existing products."},
                status=status.HTTP_409_CONFLICT,
            )


class ProductAPIView(PaginatedAPIView):
    parser_classes = [MultiPartParser, FormParser]

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

        queryset = Product.objects.select_related(
            "brand", "category", "subcategory"
        ).prefetch_related(
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
            queryset = queryset.filter(is_active=True)

        if request.query_params.get("top_selling", "").lower() == "true":
            queryset = queryset.filter(top_selling=True)
        if request.query_params.get("featured", "").lower() == "true":
            queryset = queryset.filter(featured=True)
        if request.query_params.get("new_arrival", "").lower() == "true":
            queryset = queryset.filter(new_arrival=True)

        category_id = request.query_params.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        subcategory_id = request.query_params.get("subcategory")
        if subcategory_id:
            queryset = queryset.filter(subcategory_id=subcategory_id)

        response = self.paginate(request, queryset, ProductSerializer)

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


class ProductDetailAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    @cache_product_detail(timeout=300)
    def get(self, request, pk):
        queryset = Product.objects.select_related(
            "brand", "category", "subcategory"
        ).prefetch_related(
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
        if not (request.user.is_authenticated and request.user.is_staff):
            queryset = queryset.filter(is_active=True)
        product = get_object_or_404(queryset, pk=pk)

        if request.user.is_authenticated:
            from .models import RecentlyViewedProduct
            RecentlyViewedProduct.objects.update_or_create(
                user=request.user,
                product=product,
            )

        return Response(CachedProductSerializer(product, context={"request": request}).data)

    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(
            product, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        """
        Delete a product and AGGRESSIVELY invalidate every cache that could
        still reference it. This fixes the "ghost product" bug where a deleted
        item kept appearing on the admin list until the 5-minute cache TTL
        elapsed, leading users to click delete again and get 404 errors.

        Belt-and-suspenders: the post_delete signal in core/signals.py also
        clears these caches, but signals can be bypassed (queryset.delete(),
        raw SQL) or silently fail (IGNORE_EXCEPTIONS=True on the cache).
        Doing it inline guarantees the next list GET sees fresh data.
        """
        product = get_object_or_404(Product, pk=pk)
        product_id = product.id

        try:
            product.delete()
        except ProtectedError:
            return Response(
                {
                    "error": "Cannot delete this product permanently because it is linked to existing orders. "
                             "Please set it to Inactive instead."
                },
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
            logger.error(
                f"Explicit cache wipe FAILED after deleting product {product_id}: {e}",
                exc_info=True,
            )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        response["Cache-Control"] = "no-store"
        return response


class ProductListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        search_query = request.query_params.get("search", "").strip()
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            page, page_size = 1, 20

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
            search_result = ElasticsearchSearchManager.search(
                search_query, **search_params)
        except Exception as e:
            logger.warning(
                f"Elasticsearch search failed, falling back to DB: {e}")

        if search_result:
            product_ids = search_result["ids"]
            preserved_order = {pid: pos for pos, pid in enumerate(product_ids)}
            queryset = Product.objects.filter(id__in=product_ids).select_related(
                "brand", "category"
            ).prefetch_related(
                Prefetch("related_products", queryset=Product.objects.filter(is_active=True), to_attr="active_related_products"),
                Prefetch("frequently_bought_together", queryset=Product.objects.filter(is_active=True), to_attr="active_fbt_products"),
            )
            products = sorted(
                queryset, key=lambda x: preserved_order.get(str(x.id), 0))
            serializer = ProductSerializer(
                products, many=True, context={"request": request})
            return Response({
                "count": search_result["total"],
                "results": serializer.data,
                "took": search_result.get("took"),
                "page": page,
                "page_size": page_size,
            })

        queryset = Product.objects.filter(is_active=True).select_related(
            "brand", "category"
        ).prefetch_related(
            Prefetch("related_products", queryset=Product.objects.filter(is_active=True), to_attr="active_related_products"),
            Prefetch("frequently_bought_together", queryset=Product.objects.filter(is_active=True), to_attr="active_fbt_products"),
        )
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(
                    description__icontains=search_query)
            )
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        page_obj = paginator.paginate_queryset(queryset, request)
        serializer = ProductSerializer(
            page_obj, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class RecentlyViewedProductsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import RecentlyViewedProduct
        history = RecentlyViewedProduct.objects.filter(
            user=request.user,
            product__is_active=True
        ).select_related("product", "product__brand", "product__category")[:10]

        products = [h.product for h in history]
        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data)


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
            .order_by("-rating")[:limit]
        )
        return Response({
            "current_product": ProductSerializer(product).data,
            "similar_products": ProductSerializer(similar, many=True).data,
            "count": len(similar),
        })



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
        serializer = ProductImageSerializer(
            data=request.data, context={"request": request})
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
        image_obj = get_object_or_404(
            ProductImage.objects.select_related("product"), pk=pk
        )
        return Response(ProductImageSerializer(image_obj, context={"request": request}).data)

    def put(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        serializer = ProductImageSerializer(
            image_obj, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        image_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



class ProductSpecificationListAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = ProductSpecification.objects.select_related("product").order_by(
            "product_id", "section", "key", "id"
        )
        product_id = request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return self.paginate(request, queryset, ProductSpecificationSerializer)

    def post(self, request):
        serializer = ProductSpecificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductSpecificationDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        spec = get_object_or_404(
            ProductSpecification.objects.select_related("product"), pk=pk
        )
        return Response(ProductSpecificationSerializer(spec).data)

    def put(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        serializer = ProductSpecificationSerializer(
            spec, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        spec.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)



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

        uploaded_images = {}
        for image_file in request.FILES.getlist("images"):
            uploaded_images[image_file.name] = image_file

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
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )