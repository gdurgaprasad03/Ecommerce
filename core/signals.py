from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from orders.models import CustomerRequest
from inventory.models import Inventory
from products.models import Product, Category, Brand
from reviews.models import ProductReview
from wishlist.models import Wishlist
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomerRequest)
def update_inventory_on_closed_request(sender, instance, **kwargs):
    """
    Automatically decrements product stock when a customer request is marked as 'closed'.
    """
    if instance.status == CustomerRequest.STATUS_CLOSED and not instance.stock_deducted:
        try:
            inventory = Inventory.objects.select_for_update().get(product=instance.product)

            if inventory.stock >= instance.quantity:
                inventory.stock -= instance.quantity
                inventory.save()
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


# ==================== Phase 2: Cache Invalidation Signals ====================

@receiver(post_save, sender=Product)
def invalidate_product_cache(sender, instance, created, **kwargs):
    """Invalidate product cache when product is updated"""
    from core.cache_utils import CacheManager
    
    try:
        # Clear specific product cache
        CacheManager.clear_product_cache(instance.id)
        # Clear all product list caches
        CacheManager.clear_product_list_cache()
        # Clear analytics cache
        CacheManager.clear_analytics_cache()
        
        logger.debug(f"Cache invalidated for product: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for product {instance.id}: {str(e)}")


@receiver(post_save, sender=Category)
def invalidate_category_cache(sender, instance, created, **kwargs):
    """Invalidate category cache when category is updated"""
    from core.cache_utils import CacheManager
    
    try:
        CacheManager.clear_category_cache(instance.id)
        CacheManager.clear_product_list_cache()
        logger.debug(f"Cache invalidated for category: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for category {instance.id}: {str(e)}")


@receiver(post_save, sender=Brand)
def invalidate_brand_cache(sender, instance, created, **kwargs):
    """Invalidate brand cache when brand is updated"""
    from core.cache_utils import CacheManager
    
    try:
        CacheManager.clear_brand_cache(instance.id)
        CacheManager.clear_product_list_cache()
        logger.debug(f"Cache invalidated for brand: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for brand {instance.id}: {str(e)}")


@receiver(post_save, sender=Inventory)
def invalidate_inventory_cache(sender, instance, created, **kwargs):
    """Invalidate inventory cache when stock is updated"""
    from core.cache_utils import CacheManager
    
    try:
        CacheManager.delete_cache(f"product_inventory:{instance.product.id}")
        CacheManager.clear_product_cache(instance.product.id)
        
        # Send stock alert if low on stock
        if instance.stock < 10:
            from core.tasks import notify_stock_low
            notify_stock_low.delay(instance.product.id)
        
        logger.debug(f"Cache invalidated for inventory: {instance.product.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for inventory: {str(e)}")


@receiver(post_save, sender=ProductReview)
def invalidate_product_review_cache(sender, instance, created, **kwargs):
    """Invalidate review and product cache when review is updated"""
    from core.cache_utils import CacheManager
    
    try:
        CacheManager.delete_cache(f"product_reviews:{instance.product.id}")
        CacheManager.clear_product_cache(instance.product.id)
        CacheManager.clear_analytics_cache("reviews")
        logger.debug(f"Cache invalidated for product reviews: {instance.product.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for product reviews: {str(e)}")


# ==================== Phase 2: Email Notification Signals ====================

@receiver(post_save, sender=User)
def send_welcome_email_on_user_creation(sender, instance, created, **kwargs):
    """Send welcome email when new user registers"""
    if created:
        from core.tasks import send_welcome_email
        try:
            # Delay by 5 seconds to ensure user is fully created
            send_welcome_email.apply_async(args=[instance.id], countdown=5)
            logger.info(f"Welcome email task queued for user: {instance.email}")
        except Exception as e:
            logger.error(f"Error queuing welcome email for user {instance.id}: {str(e)}")


# ==================== Phase 2: Elasticsearch Indexing Signals ====================

@receiver(post_save, sender=Product)
def index_product_in_elasticsearch(sender, instance, created, **kwargs):
    """Index product in Elasticsearch when created/updated"""
    if instance.is_active:
        from search.search import ElasticsearchSearchManager
        try:
            ElasticsearchSearchManager.index_product(instance)
            logger.debug(f"Product {instance.id} indexed in Elasticsearch")
        except Exception as e:
            logger.warning(f"Error indexing product {instance.id} in Elasticsearch: {str(e)}")


@receiver(post_delete, sender=Product)
def remove_product_from_elasticsearch(sender, instance, **kwargs):
    """Remove product from Elasticsearch index when deleted"""
    from search.search import ElasticsearchSearchManager
    try:
        ElasticsearchSearchManager.delete_product_index(instance.id)
        logger.debug(f"Product {instance.id} removed from Elasticsearch")
    except Exception as e:
        logger.warning(f"Error removing product {instance.id} from Elasticsearch: {str(e)}")
