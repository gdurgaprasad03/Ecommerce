import multiprocessing
import os
import logging

logger = logging.getLogger(__name__)

try:
    bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
    workers = int(os.getenv("GUNICORN_WORKERS", str(2 * multiprocessing.cpu_count() + 1)))
    threads = int(os.getenv("GUNICORN_THREADS", "4"))
    worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
    max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
    max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
    timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
    graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
    keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
    preload_app = True
    accesslog = "-"
    errorlog = "-"
    loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
    access_log_format = (
        '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
        '"%(f)s" "%(a)s" %(L)ss'
    )
    logger.info(f"Gunicorn configuration loaded: workers={workers}, threads={threads}")
except Exception as e:
    logger.error(f"Error loading gunicorn configuration: {str(e)}", exc_info=True)
    raise
