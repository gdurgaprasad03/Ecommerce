"""Django's command-line utility for administrative tasks."""
import os
import sys

def suppress_socketserver_timeouts():
    """Suppress harmless TimeoutError logs from development server."""
    import socketserver
    original_handle_error = socketserver.BaseServer.handle_error
    def custom_handle_error(self, request, client_address):
        if sys.exc_info()[0] is TimeoutError:
            return
        original_handle_error(self, request, client_address)
    socketserver.BaseServer.handle_error = custom_handle_error

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    if 'runserver' in sys.argv:
        suppress_socketserver_timeouts()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
