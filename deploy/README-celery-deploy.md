# Celery on the server (production)

Emails (enquiry admin + customer confirmation, password-reset is synchronous, welcome,
stock alerts, etc.) are sent **asynchronously** by a Celery worker consuming the `emails`
queue. If the worker is not running, those emails are queued in Redis but never sent.

## 1. Verify Redis is running
```bash
redis-cli -n 1 ping        # should print: PONG  (broker is redis://127.0.0.1:6379/1)
sudo systemctl enable --now redis-server
```

## 2. Install the systemd units
```bash
sudo cp /var/www/sales/backend/deploy/celery-worker.service /etc/systemd/system/
sudo cp /var/www/sales/backend/deploy/celery-beat.service   /etc/systemd/system/

# IMPORTANT: edit User/Group in both files to match who owns /var/www/sales
#   (run: stat -c '%U' /var/www/sales/backend  to find the owner)

sudo systemctl daemon-reload
sudo systemctl enable --now celery-worker.service
sudo systemctl enable --now celery-beat.service
```

## 3. Confirm it's consuming the emails queue
```bash
sudo systemctl status celery-worker.service
# In the log you should see the queues:  [queues] celery, emails, alerts, analytics

# Live logs:
journalctl -u celery-worker.service -f
```

## 4. Test end to end
Submit an enquiry from the site, then watch the worker log:
```bash
journalctl -u celery-worker.service -f
# expect:  Task core.tasks.send_enquiry_email[...] received
#          Admin notification sent for enquiry <id>
#          Customer confirmation sent for enquiry <id>
```

## 5. After each deploy
```bash
sudo systemctl restart celery-worker.service celery-beat.service
```
Restart the worker whenever you change task code (`core/tasks.py`) — it loads code at startup.

---

## Prerequisites for delivery (env in /var/www/sales/backend/.env)
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — SMTP creds (Gmail: use an App Password)
- `DEFAULT_FROM_EMAIL` — the From address
- `SALES_NOTIFICATION_EMAIL` — where the admin enquiry notification goes
- `CELERY_BROKER_URL` — defaults to redis://127.0.0.1:6379/1

## Quick diagnosis: is it the worker or SMTP?
Temporarily set `CELERY_EAGER=True` in `.env` and restart gunicorn. Tasks then run inline
in the web process:
- Emails now arrive  -> the worker/queue was the problem (use the units above, unset CELERY_EAGER).
- Emails still don't arrive -> it's SMTP/credentials; check the gunicorn log for the SMTP error.
