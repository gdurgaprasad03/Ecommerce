import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import CustomerRequest, Enquiry

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomerRequest)
def notify_admin_new_request(sender, instance, created, **kwargs):
    if created:
        subject = f"New Product Inquiry: {instance.product.name}"
        message = f"""
        You have received a new inquiry!
        
        Customer Name: {instance.name}
        Email: {instance.email}
        Phone: {instance.phone}
        Product: {instance.product.name} (SKU: {instance.product.sku})
        Quantity: {instance.quantity}
        
        Message:
        {instance.description}
        
        Please respond to the customer at your earliest convenience.
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SALES_NOTIFICATION_EMAIL],
                fail_silently=True,
            )
            logger.info(f"New inquiry notification sent for {instance.product.name}")
        except Exception as e:
            logger.error(f"Failed to send inquiry notification: {str(e)}")

@receiver(post_save, sender=Enquiry)
def notify_admin_new_enquiry(sender, instance, created, **kwargs):
    if created:
        subject = "New General/Company Enquiry"
        product_name = instance.product.name if instance.product else "General"
        message = f"""
        A new company enquiry has been received!
        
        Name: {instance.name}
        Company: {instance.company_name}
        Email: {instance.email}
        Phone: {instance.phone}
        Product: {product_name}
        Quantity: {instance.quantity}
        
        Description:
        {instance.description}
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SALES_NOTIFICATION_EMAIL],
                fail_silently=True,
            )
            logger.info("New company enquiry notification sent")
        except Exception as e:
            logger.error(f"Failed to send enquiry notification: {str(e)}")
