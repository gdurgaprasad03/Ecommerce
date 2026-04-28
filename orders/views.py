from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
import logging
from threading import Thread

from .models import CustomerRequest, Enquiry
from .serializers import CustomerRequestSerializer, CustomerRequestStatusSerializer, EnquirySerializer
from core.pagination.views import PaginatedAPIView
from core.utils.helpers import safe_send_mail

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
        request_obj = serializer.save()

        def send_email_safe(obj):
            try:
                product_name = obj.product.name if obj.product else "N/A"
                safe_send_mail(
                    f"New Product Request - {product_name}",
                    (f"New customer inquiry received.\n\nCustomer Name: {obj.name}\nEmail: {obj.email}\nPhone: {obj.phone}\nProduct: {product_name}\nQuantity: {obj.quantity}\nDescription:\n{obj.description}"),
                    [getattr(settings, "SALES_NOTIFICATION_EMAIL", "")]
                )
                safe_send_mail(
                    "We received your quote request",
                    (f"Dear {obj.name},\n\nThank you for reaching out to us.\nWe have successfully received your quote request for {product_name}.\n\nOur team will contact you soon with the pricing and further details.\n\nBest regards,\nYour Company Team"),
                    [obj.email]
                )
            except Exception:
                logger.exception("Email failed", extra={"request_id": obj.id})

        Thread(target=send_email_safe, args=(request_obj,), daemon=True).start()

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
        enquiry = serializer.save()

        def send_email_safe(obj):
            try:
                product_name = obj.product.name if obj.product else "General Enquiry"
                safe_send_mail(
                    f"New Enquiry - {product_name}",
                    (f"New enquiry received.\n\nName: {obj.name}\nCompany Name: {obj.company_name}\nCompany Address: {obj.company_address}\nEmail: {obj.email}\nPhone: {obj.phone}\nProduct: {product_name}\nQuantity: {obj.quantity}\nDescription:\n{obj.description}"),
                    [getattr(settings, "SALES_NOTIFICATION_EMAIL", "")]
                )
                safe_send_mail(
                    "Thank you for your enquiry",
                    (f"Dear {obj.name},\n\nThank you for contacting us.\nWe have received your enquiry and our team will get in touch with you shortly.\n\nProduct: {product_name}\nQuantity: {obj.quantity}\n\nBest regards,\nYour Company Team"),
                    [obj.email]
                )
            except Exception:
                logger.exception("Enquiry email failed", extra={"enquiry_id": obj.id})

        Thread(target=send_email_safe, args=(enquiry,), daemon=True).start()

        return Response({"status": True, "message": "Enquiry submitted successfully."}, status=status.HTTP_201_CREATED)
