"""
Gunicorn production config.

Start the server with:
    gunicorn -c gunicorn.conf.py config.wsgi:application

Tunables come from env vars so the same file works on dev/staging/prod.
"""
import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Workers: 2*CPU + 1 is the gunicorn-recommended starting point for CPU work.
# We override via env on small boxes (e.g. 1 vCPU droplets -> 3 workers).
workers = int(os.getenv("GUNICORN_WORKERS", str(2 * multiprocessing.cpu_count() + 1)))

# Threads per worker. Django views do I/O (DB, SMTP, Redis), so threads help
# concurrency without paying the per-process RAM cost of more workers.
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

# Recycle workers periodically to bound memory leaks from third-party libs.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# Per-request limits.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Preload the app so workers share parsed bytecode (saves RAM, faster boot).
# Safe because we don't open DB connections at import time.
preload_app = True

# Logging — stream to stdout/stderr so the platform (systemd / Docker /
# Render / Fly) captures them. Django's own file logger still writes the
# rotated app log on top of this.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(L)ss'
)
