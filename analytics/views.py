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
        from .models import AnalyticsManager
        try:
            data = AnalyticsManager.get_all_analytics()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching unified dashboard: {str(e)}")
            return Response({"error": "Failed to fetch dashboard data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
