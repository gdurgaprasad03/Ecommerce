from django.db import models
from django.contrib.auth.models import User
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class AnalyticsSnapshot(models.Model):
    total_products_viewed = models.IntegerField(default=0)
    total_products = models.IntegerField(default=0)
    featured_products_count = models.IntegerField(default=0)
    top_selling_products_count = models.IntegerField(default=0)
    new_arrivals_count = models.IntegerField(default=0)
    
    total_users = models.IntegerField(default=0)
    active_users_today = models.IntegerField(default=0)
    active_users_this_week = models.IntegerField(default=0)
    active_users_this_month = models.IntegerField(default=0)
    new_users_today = models.IntegerField(default=0)
    new_users_this_week = models.IntegerField(default=0)
    new_users_this_month = models.IntegerField(default=0)
    
    total_reviews = models.IntegerField(default=0)
    average_rating = models.FloatField(default=0.0)
    five_star_reviews = models.IntegerField(default=0)
    four_star_reviews = models.IntegerField(default=0)
    three_star_reviews = models.IntegerField(default=0)
    two_star_reviews = models.IntegerField(default=0)
    one_star_reviews = models.IntegerField(default=0)
    verified_reviews = models.IntegerField(default=0)
    
    total_wishlists = models.IntegerField(default=0)
    total_wishlist_items = models.IntegerField(default=0)
    average_wishlist_size = models.FloatField(default=0.0)
    most_wishlisted_product = models.CharField(max_length=255, blank=True, null=True)
    
    total_stock_value = models.FloatField(default=0.0)
    out_of_stock_products = models.IntegerField(default=0)
    low_stock_products = models.IntegerField(default=0)
    products_with_zero_views = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]
    
    def __str__(self):
        return f"Analytics Snapshot - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ProductAnalytics(models.Model):
    product_id = models.IntegerField(db_index=True)
    product_name = models.CharField(max_length=255)
    
    views_today = models.IntegerField(default=0)
    views_this_week = models.IntegerField(default=0)
    views_this_month = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    
    reviews_count = models.IntegerField(default=0)
    average_rating = models.FloatField(default=0.0)
    
    wishlist_count = models.IntegerField(default=0)
    
    stock_quantity = models.IntegerField(default=0)
    stock_value = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-total_views"]
        indexes = [
            models.Index(fields=["product_id"]),
            models.Index(fields=["total_views"]),
        ]
    
    def __str__(self):
        return f"{self.product_name} - {self.total_views} views"


class AnalyticsManager:
    @staticmethod
    def get_sales_metrics():
        from core.cache_utils import CacheManager
        cache_key = "analytics:sales_metrics"
        cached = CacheManager.get_cache(cache_key)
        if cached:
            return cached
        
        from products.models import Product
        
        products = Product.objects.filter(is_active=True)
        data = {
            "total_products": products.count(),
            "featured_products": products.filter(featured=True).count(),
            "top_selling": products.filter(top_selling=True).count(),
            "new_arrivals": products.filter(new_arrival=True).count(),
            "most_viewed": products.order_by("-rating").first().name if products.exists() else None,
            "least_viewed": products.order_by("rating").first().name if products.exists() else None,
        }
        CacheManager.set_cache(cache_key, data, timeout=1800)
        return data
    
    @staticmethod
    def get_customer_metrics():
        from core.cache_utils import CacheManager
        cache_key = "analytics:customer_metrics"
        cached = CacheManager.get_cache(cache_key)
        if cached:
            return cached
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)
        
        users = User.objects.all()
        data = {
            "total_users": users.count(),
            "active_today": users.filter(last_login__gte=today_start).count(),
            "active_this_week": users.filter(last_login__gte=week_start).count(),
            "active_this_month": users.filter(last_login__gte=month_start).count(),
            "new_users_today": users.filter(date_joined__gte=today_start).count(),
            "new_users_this_week": users.filter(date_joined__gte=week_start).count(),
            "new_users_this_month": users.filter(date_joined__gte=month_start).count(),
        }
        CacheManager.set_cache(cache_key, data, timeout=1800)
        return data
    
    @staticmethod
    def get_review_metrics():
        from core.cache_utils import CacheManager
        cache_key = "analytics:review_metrics"
        cached = CacheManager.get_cache(cache_key)
        if cached:
            return cached
        
        from reviews.models import ProductReview
        reviews = ProductReview.objects.all()
        data = {
            "total_reviews": reviews.count(),
            "average_rating": reviews.aggregate(Avg('rating'))['rating__avg'] or 0,
            "five_star": reviews.filter(rating=5).count(),
            "four_star": reviews.filter(rating=4).count(),
            "three_star": reviews.filter(rating=3).count(),
            "two_star": reviews.filter(rating=2).count(),
            "one_star": reviews.filter(rating=1).count(),
            "verified_reviews": reviews.filter(is_verified=True).count(),
        }
        CacheManager.set_cache(cache_key, data, timeout=1800)
        return data
    
    @staticmethod
    def get_wishlist_metrics():
        from core.cache_utils import CacheManager
        cache_key = "analytics:wishlist_metrics"
        cached = CacheManager.get_cache(cache_key)
        if cached:
            return cached
        
        from wishlist.models import Wishlist
        from products.models import Product
        
        wishlists = Wishlist.objects.all()
        if wishlists.exists():
            most_wishlisted = Product.objects.annotate(
                wishlist_count=Count('in_wishlists')
            ).order_by('-wishlist_count').first()
            avg_size = wishlists.annotate(
                size=Count('products')
            ).aggregate(Avg('size'))['size__avg'] or 0
        else:
            most_wishlisted = None
            avg_size = 0
        
        data = {
            "total_wishlists": wishlists.count(),
            "total_items": sum(w.products.count() for w in wishlists),
            "average_wishlist_size": round(avg_size, 2),
            "most_wishlisted_product": most_wishlisted.name if most_wishlisted else None,
        }
        CacheManager.set_cache(cache_key, data, timeout=1800)
        return data
    
    @staticmethod
    def get_inventory_metrics():
        from core.cache_utils import CacheManager
        cache_key = "analytics:inventory_metrics"
        cached = CacheManager.get_cache(cache_key)
        if cached:
            return cached
        
        from inventory.models import Inventory
        inventory = Inventory.objects.select_related('product').all()
        out_of_stock = inventory.filter(stock=0).count()
        low_stock = inventory.filter(stock__gt=0, stock__lte=10).count()
        data = {
            "total_stock_items": inventory.count(),
            "out_of_stock": out_of_stock,
            "low_stock": low_stock,
            "total_stock_quantity": inventory.aggregate(Sum('stock'))['stock__sum'] or 0,
        }
        CacheManager.set_cache(cache_key, data, timeout=1800)
        return data
    
    @staticmethod
    def get_all_analytics():
        return {
            "sales": AnalyticsManager.get_sales_metrics(),
            "customers": AnalyticsManager.get_customer_metrics(),
            "reviews": AnalyticsManager.get_review_metrics(),
            "wishlists": AnalyticsManager.get_wishlist_metrics(),
            "inventory": AnalyticsManager.get_inventory_metrics(),
        }
