from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from products.models import Category, Product
from inventory.models import Inventory
from orders.models import CustomerRequest
import logging

logger = logging.getLogger(__name__)

class DashboardAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        low_stock_threshold = 5

        total_categories = Category.objects.filter(is_active=True).count()
        total_products = Product.objects.filter(is_active=True).count()
        total_inventory_items = Inventory.objects.count()
        total_requests = CustomerRequest.objects.count()

        pending_requests = CustomerRequest.objects.filter(status=CustomerRequest.STATUS_PENDING).count()
        quote_sent_requests = CustomerRequest.objects.filter(status=CustomerRequest.STATUS_QUOTE_SENT).count()
        closed_requests = CustomerRequest.objects.filter(status=CustomerRequest.STATUS_CLOSED).count()

        low_stock_products = Inventory.objects.select_related("product").filter(stock__lte=low_stock_threshold)
        top_selling_products = Product.objects.filter(is_active=True, top_selling=True)[:10]
        recent_requests = CustomerRequest.objects.select_related("product").order_by("-created_at")[:10]

        return Response({
            "summary": {
                "total_categories": total_categories, "total_products": total_products,
                "total_inventory_items": total_inventory_items, "total_requests": total_requests,
                "pending_requests": pending_requests, "quote_sent_requests": quote_sent_requests,
                "closed_requests": closed_requests,
            },
            "low_stock_products": [
                {"id": item.product.id, "name": item.product.name, "brand": item.product.brand.name if item.product.brand else None, "stock": item.stock} for item in low_stock_products
            ],
            "top_selling_products": [
                {"id": product.id, "name": product.name, "brand": product.brand.name if product.brand else None, "category": product.category.name if product.category else None} for product in top_selling_products
            ],
            "recent_requests": [
                {"id": req.id, "name": req.name, "email": req.email, "product": req.product.name if req.product else None, "quantity": req.quantity, "status": req.status, "created_at": req.created_at} for req in recent_requests
            ],
        }, status=status.HTTP_200_OK)

class AnalyticsBaseAPIView(APIView):
    permission_classes = [IsAdminUser]

class SalesAnalyticsAPIView(AnalyticsBaseAPIView):
    def get(self, request):
        from .models import AnalyticsManager
        try: return Response(AnalyticsManager.get_sales_metrics(), status=status.HTTP_200_OK)
        except Exception as e: return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerAnalyticsAPIView(AnalyticsBaseAPIView):
    def get(self, request):
        from .models import AnalyticsManager
        try: return Response(AnalyticsManager.get_customer_metrics(), status=status.HTTP_200_OK)
        except Exception as e: return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReviewAnalyticsAPIView(AnalyticsBaseAPIView):
    def get(self, request):
        from .models import AnalyticsManager
        try: return Response(AnalyticsManager.get_review_metrics(), status=status.HTTP_200_OK)
        except Exception as e: return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class WishlistAnalyticsAPIView(AnalyticsBaseAPIView):
    def get(self, request):
        from .models import AnalyticsManager
        try: return Response(AnalyticsManager.get_wishlist_metrics(), status=status.HTTP_200_OK)
        except Exception as e: return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InventoryAnalyticsAPIView(AnalyticsBaseAPIView):
    def get(self, request):
        from .models import AnalyticsManager
        try: return Response(AnalyticsManager.get_inventory_metrics(), status=status.HTTP_200_OK)
        except Exception as e: return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ComprehensiveAnalyticsAPIView(AnalyticsBaseAPIView):
    def get(self, request):
        from .models import AnalyticsManager
        try: return Response(AnalyticsManager.get_all_analytics(), status=status.HTTP_200_OK)
        except Exception as e: return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
