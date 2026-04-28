from django.urls import path
from .views import CustomerRequestAPIView, EnquiryAPIView

urlpatterns = [
    path("requests/", CustomerRequestAPIView.as_view(), name="request-list-create"),
    path("requests/<int:pk>/", CustomerRequestAPIView.as_view(), name="request-detail"),
    path("enquiries/", EnquiryAPIView.as_view(), name="enquiry-list-create"),
]
