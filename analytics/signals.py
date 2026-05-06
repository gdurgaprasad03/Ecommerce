from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from inventory.models import Inventory
from core.cache_utils import CacheManager

@receiver(post_save, sender=Inventory)
@receiver(post_delete, sender=Inventory)
def clear_inventory_analytics_cache(sender, instance, **kwargs):
    """
    Clear the inventory analytics cache whenever an Inventory item is updated or deleted.
    """
    cache_key = "analytics:inventory_metrics"
    CacheManager.delete_cache(cache_key)

    CacheManager.delete_cache("analytics:comprehensive")
