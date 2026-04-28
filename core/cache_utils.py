"""
Cache utility functions for Phase 2 - Caching & Performance Optimization
Provides functions to manage caching for products, categories, and brands
"""

from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Cache key prefixes
PRODUCT_CACHE_PREFIX = "product:"
CATEGORY_CACHE_PREFIX = "category:"
BRAND_CACHE_PREFIX = "brand:"
PRODUCT_LIST_CACHE_PREFIX = "product_list:"
ANALYTICS_CACHE_PREFIX = "analytics:"

# Cache timeouts
DEFAULT_CACHE_TIMEOUT = settings.CACHES['default'].get('TIMEOUT', 3600)
SHORT_CACHE_TIMEOUT = 300  # 5 minutes
LONG_CACHE_TIMEOUT = 86400  # 24 hours


class CacheManager:
    """Manages application caching operations"""

    @staticmethod
    def get_cache_key(prefix: str, identifier) -> str:
        """Generate a cache key"""
        return f"{prefix}{identifier}"

    @staticmethod
    def get_product_cache_key(product_id: int) -> str:
        """Get cache key for a specific product"""
        return CacheManager.get_cache_key(PRODUCT_CACHE_PREFIX, product_id)

    @staticmethod
    def get_category_cache_key(category_id: int) -> str:
        """Get cache key for a specific category"""
        return CacheManager.get_cache_key(CATEGORY_CACHE_PREFIX, category_id)

    @staticmethod
    def get_brand_cache_key(brand_id: int) -> str:
        """Get cache key for a specific brand"""
        return CacheManager.get_cache_key(BRAND_CACHE_PREFIX, brand_id)

    @staticmethod
    def get_product_list_cache_key(filters_hash: str) -> str:
        """Get cache key for product list with specific filters"""
        return f"{PRODUCT_LIST_CACHE_PREFIX}{filters_hash}"

    @staticmethod
    def get_analytics_cache_key(metric: str, period: str = "all") -> str:
        """Get cache key for analytics data"""
        return f"{ANALYTICS_CACHE_PREFIX}{metric}:{period}"

    @staticmethod
    def set_cache(key: str, value, timeout: int = DEFAULT_CACHE_TIMEOUT) -> bool:
        """
        Set a cache value
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.set(key, value, timeout)
            logger.debug(f"Cache set: {key} (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Error setting cache for {key}: {str(e)}")
            return False

    @staticmethod
    def get_cache(key: str, default=None):
        """
        Get a cache value
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default)
            if value is not None:
                logger.debug(f"Cache hit: {key}")
            else:
                logger.debug(f"Cache miss: {key}")
            return value
        except Exception as e:
            logger.error(f"Error getting cache for {key}: {str(e)}")
            return default

    @staticmethod
    def delete_cache(key: str) -> bool:
        """
        Delete a cache value
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache for {key}: {str(e)}")
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> bool:
        """
        Delete all cache keys matching a pattern
        
        Args:
            pattern: Pattern to match (e.g., "product:*")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cache.delete_pattern(pattern)
            logger.debug(f"Cache pattern deleted: {pattern}")
            return True
        except Exception as e:
            logger.warning(f"Error deleting cache pattern {pattern}: {str(e)}")
            return False

    @staticmethod
    def clear_product_cache(product_id: int = None) -> bool:
        """
        Clear product cache
        
        Args:
            product_id: Specific product ID to clear, or None to clear all products
            
        Returns:
            True if successful, False otherwise
        """
        if product_id:
            return CacheManager.delete_cache(CacheManager.get_product_cache_key(product_id))
        else:
            return CacheManager.delete_pattern(f"{PRODUCT_CACHE_PREFIX}*")

    @staticmethod
    def clear_category_cache(category_id: int = None) -> bool:
        """Clear category cache"""
        if category_id:
            return CacheManager.delete_cache(CacheManager.get_category_cache_key(category_id))
        else:
            return CacheManager.delete_pattern(f"{CATEGORY_CACHE_PREFIX}*")

    @staticmethod
    def clear_brand_cache(brand_id: int = None) -> bool:
        """Clear brand cache"""
        if brand_id:
            return CacheManager.delete_cache(CacheManager.get_brand_cache_key(brand_id))
        else:
            return CacheManager.delete_pattern(f"{BRAND_CACHE_PREFIX}*")

    @staticmethod
    def clear_product_list_cache() -> bool:
        """Clear all product list caches"""
        return CacheManager.delete_pattern(f"{PRODUCT_LIST_CACHE_PREFIX}*")

    @staticmethod
    def clear_analytics_cache(metric: str = None) -> bool:
        """Clear analytics cache"""
        if metric:
            return CacheManager.delete_pattern(f"{ANALYTICS_CACHE_PREFIX}{metric}:*")
        else:
            return CacheManager.delete_pattern(f"{ANALYTICS_CACHE_PREFIX}*")

    @staticmethod
    def clear_all_cache() -> bool:
        """Clear all application cache"""
        try:
            cache.clear()
            logger.info("All cache cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing all cache: {str(e)}")
            return False


def cache_decorator(timeout: int = DEFAULT_CACHE_TIMEOUT, key_prefix: str = ""):
    """
    Decorator to cache function results
    
    Usage:
        @cache_decorator(timeout=600, key_prefix="my_func")
        def expensive_function(arg1, arg2):
            return expensive_calculation(arg1, arg2)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix or func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = cache_key.replace(" ", "").replace("'", "")
            
            # Try to get from cache
            result = CacheManager.get_cache(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            CacheManager.set_cache(cache_key, result, timeout)
            return result
        
        return wrapper
    return decorator
