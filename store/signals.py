from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomerRequest, Inventory
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomerRequest)
def update_inventory_on_closed_request(sender, instance, **kwargs):
    """
    Automatically decrements product stock when a customer request is marked as 'closed'.
    """
    if instance.status == CustomerRequest.STATUS_CLOSED and not instance.stock_deducted:
        try:
            # We use select_for_update() to prevent race conditions during the stock decrement
            inventory = Inventory.objects.select_for_update().get(product=instance.product)
            
            if inventory.stock >= instance.quantity:
                inventory.stock -= instance.quantity
                inventory.save()
                
                # Mark as deducted to avoid double-decrement if the record is saved again
                # Using update_fields to avoid re-triggering signal recursively or overwriting other changes
                CustomerRequest.objects.filter(pk=instance.pk).update(stock_deducted=True)
                
                logger.info(f"Inventory updated for {instance.product.name}: -{instance.quantity} units.")
            else:
                logger.warning(
                    f"Insufficient stock for {instance.product.name}. "
                    f"Available: {inventory.stock}, Requested: {instance.quantity}"
                )
                
        except Inventory.DoesNotExist:
            logger.error(f"Inventory record missing for product: {instance.product.name}")
        except Exception as e:
            logger.exception(f"Failed to update inventory for request {instance.id}: {str(e)}")
