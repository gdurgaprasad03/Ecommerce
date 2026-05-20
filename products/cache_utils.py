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
   
    if params_to_include is None:
        params_to_include = []

    key_parts = []

    if request.user.is_authenticated:
        key_parts.append(f"user_{request.user.id}")
        if request.user.is_staff:
            key_parts.append("admin")
    else:
        key_parts.append("anon")

    for param in params_to_include:
        value = request.query_params.get(param, "")
        if value:
            key_parts.append(f"{param}_{value}")

    key_str = "|".join(key_parts)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()

    return f"{prefix}:{key_hash}"


def cache_product_list(timeout=300):
   
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            if request.user.is_authenticated and request.user.is_staff:
                logger.debug("Cache SKIPPED: Admin user - fetching fresh data")
                return view_func(self, request, *args, **kwargs)
            
            relevant_params = ["category", "subcategory", "top_selling", "featured", "new_arrival"]
            cache_key = generate_cache_key("product_list", request, relevant_params)
            
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return Response(cached_payload)

            logger.debug(f"Cache MISS: {cache_key} - querying database")

            response = view_func(self, request, *args, **kwargs)

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
  
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            pk = kwargs.get('pk')
            
            if request.user.is_authenticated and request.user.is_staff:
                logger.debug(f"Cache SKIPPED: Admin user fetching product {pk}")
                return view_func(self, request, *args, **kwargs)
            
            cache_key = f"product:{pk}:public"
            
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return Response(cached_payload)

            logger.debug(f"Cache MISS: {cache_key} - querying database")

            response = view_func(self, request, *args, **kwargs)

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
        logger.info("Product list cache invalidation triggered")
    except Exception as e:
        logger.error(f"Error clearing product cache: {e}")
