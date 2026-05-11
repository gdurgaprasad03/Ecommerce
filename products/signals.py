from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Product, ProductImage, ProductSpecification

def clear_product_cache(product_id=None):
    """
    Clears the cache for product lists, search, and specific product details.
    """
    # Clear the list and search caches (using key prefixes)
    # Note: django-redis allows deleting by pattern if using the right backend, 
    # but for standard django cache we can just clear known prefixes or use a versioning strategy.
    # Here we clear the main prefixes.
    cache.delete_pattern("ecommerce:product_list:*")
    cache.delete_pattern("ecommerce:product_search:*")
    
    if product_id:
        cache.delete_pattern(f"ecommerce:product_detail:*:*") # Standard cache_page key format
        # Also clear the custom cached data used in CachedProductSerializer
        cache.delete(f"product_images:{product_id}")
        cache.delete(f"product_specs:{product_id}")
        cache.delete(f"product_reviews:{product_id}")
        cache.delete(f"product_inventory:{product_id}")

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def product_changed(sender, instance, **kwargs):
    clear_product_cache(instance.id)

@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
def product_image_changed(sender, instance, **kwargs):
    clear_product_cache(instance.product_id)

@receiver(post_save, sender=ProductSpecification)
@receiver(post_delete, sender=ProductSpecification)
def product_spec_changed(sender, instance, **kwargs):
    clear_product_cache(instance.product_id)
