from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.db import IntegrityError
import logging

from .models import CustomerRequest, Enquiry
from .serializers import CustomerRequestSerializer, CustomerRequestStatusSerializer, EnquirySerializer
from core.pagination.views import PaginatedAPIView
from core.tasks import send_customer_request_email, send_enquiry_email

logger = logging.getLogger(__name__)

class CustomerRequestAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["POST", "GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = CustomerRequest.objects.select_related("product").all()
        return self.paginate(request, queryset, CustomerRequestSerializer)

    def post(self, request):
        serializer = CustomerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            request_obj = serializer.save()

            send_customer_request_email.delay(request_obj.id)
        except IntegrityError as e:
            logger.error(f"Database error creating customer request: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create request due to duplicate entry"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error creating customer request: {str(e)}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"status": True, "message": "Request submitted successfully."}, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        req = get_object_or_404(CustomerRequest, pk=pk)
        serializer = CustomerRequestStatusSerializer(req, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Status updated successfully.", "status": req.status}, status=status.HTTP_200_OK)

class EnquiryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method in ["POST", "GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Enquiry.objects.select_related("product").all()
        return self.paginate(request, queryset, EnquirySerializer)

    def post(self, request):
        serializer = EnquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            enquiry = serializer.save()

            send_enquiry_email.delay(enquiry.id)
        except IntegrityError as e:
            logger.error(f"Database error creating enquiry: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to create enquiry due to duplicate entry"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error creating enquiry: {str(e)}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"status": True, "message": "Enquiry submitted successfully."}, status=status.HTTP_201_CREATED)
