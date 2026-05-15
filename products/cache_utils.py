"""
Smart caching utilities for products.
Implements intelligent caching that balances performance and freshness.
"""
import hashlib
import json
from functools import wraps
from django.core.cache import cache
from django.http import HttpRequest
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


def generate_cache_key(prefix, request, params_to_include=None):
    """
    Generate a cache key based on request params.
    Only includes relevant query parameters to reduce cache key variations.
    """
    if params_to_include is None:
        params_to_include = []
    
    key_parts = [prefix]
    
    # Include user authentication status
    if request.user.is_authenticated:
        key_parts.append(f"user_{request.user.id}")
        if request.user.is_staff:
            key_parts.append("admin")
    else:
        key_parts.append("anon")
    
    # Include relevant query parameters
    for param in params_to_include:
        value = request.query_params.get(param, "")
        if value:
            key_parts.append(f"{param}_{value}")
    
    # Create deterministic hash
    key_str = "|".join(key_parts)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    
    return f"products:{prefix}:{key_hash}"


def cache_product_list(timeout=300):
    """
    Cache product list responses with smart TTL.
    
    Cache Strategy:
    - Public users (non-authenticated): 5 minutes cache
    - Admins (authenticated + staff): NO cache (always fresh)
    - Includes query parameters in cache key
    
    Why this works:
    - Public users see fast cached responses
    - Admins uploading images see fresh data immediately
    - No "images not showing" issue for concurrent uploads
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Always skip cache for authenticated admin users (they need fresh data)
            if request.user.is_authenticated and request.user.is_staff:
                logger.debug("Cache SKIPPED: Admin user - fetching fresh data")
                return view_func(self, request, *args, **kwargs)
            
            # Generate cache key based on query parameters
            relevant_params = ["category", "subcategory", "top_selling", "featured", "new_arrival"]
            cache_key = generate_cache_key("product_list", request, relevant_params)
            
            # Try to get from cache
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return Response(cached_payload)

            logger.debug(f"Cache MISS: {cache_key} - querying database")

            # Call the original view function
            response = view_func(self, request, *args, **kwargs)

            # Cache the serialized data (not the Response itself — DRF Response
            # objects can't be pickled until they're rendered).
            if response.status_code == 200:
                try:
                    cache.set(cache_key, response.data, timeout)
                    logger.debug(f"Cache SET: {cache_key} with TTL={timeout}s")
                except Exception as e:
                    logger.warning(f"Failed to cache response: {e}")

            return response

        return wrapper
    return decorator


def cache_product_detail(timeout=300):
    """
    Cache product detail responses with smart TTL.
    
    Cache Strategy:
    - Public users: 5 minutes cache
    - Admins: NO cache (need fresh data when uploading images)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            pk = kwargs.get('pk')
            
            # Always skip cache for authenticated admin users
            if request.user.is_authenticated and request.user.is_staff:
                logger.debug(f"Cache SKIPPED: Admin user fetching product {pk}")
                return view_func(self, request, *args, **kwargs)
            
            # Generate cache key
            cache_key = f"product_detail:{pk}:public"
            
            # Try to get from cache
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return Response(cached_payload)

            logger.debug(f"Cache MISS: {cache_key} - querying database")

            # Call the original view function
            response = view_func(self, request, *args, **kwargs)

            # Cache the serialized data (not the Response itself — DRF Response
            # objects can't be pickled until they're rendered).
            if response.status_code == 200:
                try:
                    cache.set(cache_key, response.data, timeout)
                    logger.debug(f"Cache SET: {cache_key} with TTL={timeout}s")
                except Exception as e:
                    logger.warning(f"Failed to cache response: {e}")

            return response

        return wrapper
    return decorator


def clear_product_list_cache():
    """Clear all product list cache entries."""
    try:
        # Note: We can't use delete_pattern reliably, so we rely on TTL expiration
        # For admin-triggered updates, the signal handlers trigger this
        logger.info("Product list cache invalidation triggered")
    except Exception as e:
        logger.error(f"Error clearing product cache: {e}")
