web: gunicorn -c gunicorn.conf.py config.wsgi:application
worker: celery -A config worker -Q celery,emails,alerts,analytics -l info --concurrency=4
beat: celery -A config beat -l info -S django
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
