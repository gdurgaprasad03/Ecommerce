import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError

from .models import Inventory
from .serializers import InventorySerializer
from products.models import Product
from core.pagination.views import PaginatedAPIView

logger = logging.getLogger(__name__)

class InventoryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET": return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        try:
            queryset = Inventory.objects.select_related("product").all()
            return self.paginate(request, queryset, InventorySerializer)
        except Exception as e:
            logger.error(f"Error fetching inventory list: {str(e)}", exc_info=True)
            return Response({"error": "Failed to fetch inventory"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            product_id = request.data.get("product")
            stock = request.data.get("stock")
            if product_id is None or stock is None:
                return Response({"error": "product and stock are required."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                logger.warning(f"Product not found: {product_id}")
                return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
            try:
                inventory, created = Inventory.objects.update_or_create(product=product, defaults={"stock": stock})
                serializer = InventorySerializer(inventory)
                return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            except IntegrityError as e:
                logger.error(f"Integrity error creating inventory: {str(e)}")
                return Response({"error": "Failed to create inventory"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error in inventory POST: {str(e)}", exc_info=True)
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InventoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET": return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        try:
            inventory = get_object_or_404(Inventory.objects.select_related("product"), pk=pk)
            serializer = InventorySerializer(inventory)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching inventory detail: {str(e)}")
            return Response({"error": "Failed to fetch inventory"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk):
        try:
            inventory = get_object_or_404(Inventory, pk=pk)
            serializer = InventorySerializer(inventory, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        except IntegrityError as e:
            logger.error(f"Integrity error updating inventory: {str(e)}")
            return Response({"error": "Failed to update inventory"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating inventory: {str(e)}", exc_info=True)
            return Response({"error": "Failed to update inventory"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
