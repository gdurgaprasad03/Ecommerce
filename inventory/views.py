from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Inventory
from .serializers import InventorySerializer
from products.models import Product
from core.pagination.views import PaginatedAPIView

class InventoryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET": return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Inventory.objects.select_related("product").all()
        return self.paginate(request, queryset, InventorySerializer)

    def post(self, request):
        product_id = request.data.get("product")
        stock = request.data.get("stock")
        if product_id is None or stock is None:
            return Response({"error": "product and stock are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        inventory, created = Inventory.objects.update_or_create(product=product, defaults={"stock": stock})
        serializer = InventorySerializer(inventory)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class InventoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET": return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        inventory = get_object_or_404(Inventory.objects.select_related("product"), pk=pk)
        serializer = InventorySerializer(inventory)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        inventory = get_object_or_404(Inventory, pk=pk)
        serializer = InventorySerializer(inventory, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
