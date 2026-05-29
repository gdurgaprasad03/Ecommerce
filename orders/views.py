import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from django.conf import settings
from django.db import IntegrityError, DatabaseError

from .models import CustomerRequest, Enquiry
from .serializers import CustomerRequestSerializer, CustomerRequestStatusSerializer, EnquirySerializer
from core.pagination.views import PaginatedAPIView
from core.tasks import send_customer_request_email, send_enquiry_email, send_quote_status_email

logger = logging.getLogger(__name__)


class CustomerRequestAPIView(PaginatedAPIView):
    throttle_scope = "inquiry"

    def get_permissions(self):
        if self.request.method in ["POST", "GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        try:
            queryset = CustomerRequest.objects.select_related("product").all()
            return self.paginate(request, queryset, CustomerRequestSerializer)
        except Exception as e:
            logger.error(f"Error fetching customer requests: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to fetch requests"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = CustomerRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                request_obj = serializer.save()
                try:
                    send_customer_request_email.delay(request_obj.id)
                except Exception as e:
                    logger.warning(f"Failed to queue email task: {str(e)}")
            except IntegrityError as e:
                logger.error(f"Database error creating customer request: {str(e)}", exc_info=True)
                return Response(
                    {"error": "Failed to create request due to duplicate entry"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except DatabaseError as e:
                logger.error(f"Database error: {str(e)}", exc_info=True)
                return Response(
                    {"error": "Database error occurred"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {"status": True, "message": "Request submitted successfully."},
                status=status.HTTP_201_CREATED,
            )

        except ValidationError:
            raise  # returns 400 with field errors

        except Exception as e:
            logger.error(f"Unexpected error creating customer request: {str(e)}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, pk):
        try:
            req = get_object_or_404(CustomerRequest, pk=pk)
            old_status = req.status

            serializer = CustomerRequestStatusSerializer(req, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            new_status = req.status

            # Send status update email to customer when status changes
            if old_status != new_status:
                try:
                    send_quote_status_email.delay(req.id, new_status)
                    logger.info(
                        f"Quote status email queued for request {pk}: "
                        f"{old_status} → {new_status}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to queue status update email for request {pk}: {str(e)}"
                    )

            return Response(
                {
                    "message": "Status updated successfully.",
                    "status": new_status,
                    "email_sent": old_status != new_status,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error updating customer request: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to update request"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EnquiryAPIView(PaginatedAPIView):
    throttle_scope = "inquiry"

    def get_permissions(self):
        if self.request.method in ["POST", "GET", "OPTIONS"]:
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        try:
            queryset = Enquiry.objects.select_related("product").all()
            return self.paginate(request, queryset, EnquirySerializer)
        except Exception as e:
            logger.error(f"Error fetching enquiries: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to fetch enquiries"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = EnquirySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                enquiry = serializer.save()
              
                try:
                    send_enquiry_email.delay(enquiry.id)
                except Exception as e:
                    logger.warning(f"Failed to queue enquiry email task: {str(e)}")
            except IntegrityError as e:
                logger.error(f"Database error creating enquiry: {str(e)}", exc_info=True)
                return Response(
                    {"error": "Failed to create enquiry due to duplicate entry"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except DatabaseError as e:
                logger.error(f"Database error: {str(e)}", exc_info=True)
                return Response(
                    {"error": "Database error occurred"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {"status": True, "message": "Enquiry submitted successfully."},
                status=status.HTTP_201_CREATED,
            )

        except ValidationError:
            raise  # returns 400 with field errors — fixes the 500 bug

        except Exception as e:
            logger.error(f"Unexpected error creating enquiry: {str(e)}", exc_info=True)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )