import logging

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination.views import PaginatedAPIView
from .models import Brand, Category, Product, ProductImage, ProductSpecification
from .serializers import (
    BrandSerializer, CategoryReadSerializer, CategorySerializer,
    CategoryWriteSerializer, ProductImageSerializer, ProductSerializer,
    ProductSpecificationSerializer
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
        serializer = BrandSerializer(brand, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        serializer = BrandSerializer(brand, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        try:
            brand.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response({"error": "Cannot delete this brand because it is linked to existing products."}, status=status.HTTP_409_CONFLICT)

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
        
        from .serializers import CategorySimpleSerializer
        serializer_class = CategorySerializer if is_tree else CategorySimpleSerializer
        return self.paginate(request, queryset, serializer_class)

    def post(self, request):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class  CategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(Category.objects.prefetch_related("subcategories").filter(is_active=True), pk=pk)
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        try:
            category.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response({"error": "Cannot delete this category because it is linked to existing products or subcategories."}, status=status.HTTP_409_CONFLICT)

class   SubCategoryAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(Category.objects.prefetch_related("subcategories").filter(is_active=True), pk=pk)
        serializer = CategoryReadSerializer(category.subcategories.filter(is_active=True), many=True, context={"depth": 0})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        parent_category = get_object_or_404(Category, pk=pk)
        data = request.data.copy()
        data["parent"] = parent_category.id
        serializer = CategoryWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ProductAPIView(PaginatedAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        include_inactive = request.user.is_authenticated and request.user.is_staff and request.query_params.get("include_inactive", "").lower() == "true"
        queryset = Product.objects.select_related("brand", "category", "subcategory")
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        top_selling = request.query_params.get("top_selling")
        featured = request.query_params.get("featured")
        new_arrival = request.query_params.get("new_arrival")
        category_id = request.query_params.get("category")
        subcategory_id = request.query_params.get("subcategory")
        if top_selling and top_selling.lower() == "true": queryset = queryset.filter(top_selling=True)
        if featured and featured.lower() == "true": queryset = queryset.filter(featured=True)
        if new_arrival and new_arrival.lower() == "true": queryset = queryset.filter(new_arrival=True)
        if category_id: queryset = queryset.filter(category_id=category_id)
        if subcategory_id: queryset = queryset.filter(subcategory_id=subcategory_id)
        return self.paginate(request, queryset, ProductSerializer)

    def post(self, request):
        data = request.data.copy()
        data.pop("is_active", None)
        serializer = ProductSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(is_active=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ProductDetailAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        queryset = Product.objects.select_related("brand", "category", "subcategory")
        if not (request.user.is_authenticated and request.user.is_staff):
            queryset = queryset.filter(is_active=True)
        product = get_object_or_404(queryset, pk=pk)
        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this product permanently because it is linked to existing orders. Please set it to Inactive instead."},
                status=status.HTTP_409_CONFLICT
            )

class ProductListAPIView(APIView):
    def get(self, request):
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            from .documents import ProductDocument
            from elasticsearch_dsl.query import MultiMatch
            query = MultiMatch(query=search_query, fields=['name^3', 'description', 'highlights'], fuzziness='AUTO')
            search = ProductDocument.search().query(query).filter('term', is_active=True)
            queryset = search.to_queryset().select_related("brand", "category")
        else:
            queryset = Product.objects.filter(is_active=True).select_related("brand", "category")
        category_ids = []
        brand_ids = []
        subcategory_ids = []
        
        for key in request.query_params:
            values = request.query_params.getlist(key)
            if 'categories' in key or key == 'category':
                category_ids.extend(values)
            elif 'brands' in key or key == 'brand':
                brand_ids.extend(values)
            elif 'subcategories' in key or key == 'subcategory':
                subcategory_ids.extend(values)
        
        if category_ids: queryset = queryset.filter(category_id__in=list(set(category_ids)))
        if brand_ids: queryset = queryset.filter(brand_id__in=list(set(brand_ids)))
        if subcategory_ids: queryset = queryset.filter(subcategory_id__in=list(set(subcategory_ids)))
        
        sort_by = request.query_params.get("sort", "-created_at")
        valid_sorts = ["-created_at", "created_at", "-rating", "rating", "name", "-name"]
        if sort_by in valid_sorts: queryset = queryset.order_by(sort_by)
        if request.query_params.get("featured", "").lower() == "true": queryset = queryset.filter(featured=True)
        if request.query_params.get("new_arrivals", "").lower() == "true": queryset = queryset.filter(new_arrival=True)
        if request.query_params.get("top_selling", "").lower() == "true": queryset = queryset.filter(top_selling=True)
        paginator = PageNumberPagination()
        paginator.page_size = int(request.query_params.get("page_size", 10))
        page = paginator.paginate_queryset(queryset, request)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

class SimilarProductsAPIView(APIView):
    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id, is_active=True)
        limit = int(request.query_params.get("limit", 5))
        similar_products = Product.objects.filter(category=product.category, is_active=True).exclude(pk=product_id).order_by("-rating")[:limit]
        serializer = ProductSerializer(similar_products, many=True)
        return Response({
            "current_product": ProductSerializer(product).data,
            "similar_products": serializer.data,
            "count": len(similar_products)
        })

class ProductImageAPIView(PaginatedAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk=None):
        if pk:
            image = get_object_or_404(ProductImage.objects.select_related("product"), pk=pk)
            serializer = ProductImageSerializer(image, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        queryset = ProductImage.objects.select_related("product").all()
        product_id = request.query_params.get("product")
        if product_id: queryset = queryset.filter(product_id=product_id)
        return self.paginate(request, queryset, ProductImageSerializer)

    def post(self, request):
        serializer = ProductImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        serializer = ProductImageSerializer(image_obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        image_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class ProductSpecificationAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["GET", "OPTIONS"]: return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk=None):
        if pk:
            spec = get_object_or_404(ProductSpecification.objects.select_related("product"), pk=pk)
            serializer = ProductSpecificationSerializer(spec)
            return Response(serializer.data, status=status.HTTP_200_OK)
        queryset = ProductSpecification.objects.select_related("product").order_by("product_id", "section", "key", "id")
        product_id = request.query_params.get("product")
        if product_id: queryset = queryset.filter(product_id=product_id)
        return self.paginate(request, queryset, ProductSpecificationSerializer)

    def post(self, request):
        serializer = ProductSpecificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        serializer = ProductSpecificationSerializer(spec, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        spec.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class BulkProductUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        if 'excel_file' not in request.FILES:
            return Response(
                {'error': 'No Excel file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        excel_file = request.FILES['excel_file']
        uploaded_images = {}
        for image_file in request.FILES.getlist('images'):
            uploaded_images[image_file.name] = image_file
        try:
            service = BulkProductUploadService(excel_file, uploaded_images)
            result = service.upload()
            if result['success']:
                return Response(result, status=status.HTTP_201_CREATED)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Bulk upload error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
