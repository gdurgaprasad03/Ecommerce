import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Inventory

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 5

@receiver(post_save, sender=Inventory)
def check_low_stock(sender, instance, **kwargs):
    if instance.stock <= LOW_STOCK_THRESHOLD:
        product_name = instance.product.name
        subject = f"Low Stock Alert: {product_name}"
        message = f"The stock for '{product_name}' (SKU: {instance.product.sku}) is low. Current stock: {instance.stock}."
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.SALES_NOTIFICATION_EMAIL],
                fail_silently=True,
            )
            logger.info(f"Low stock alert sent for {product_name}")
        except Exception as e:
            logger.error(f"Failed to send low stock alert: {str(e)}")
