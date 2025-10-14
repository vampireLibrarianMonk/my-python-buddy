"""
WSGI config for core project.

# This file defines the WSGI (Web Server Gateway Interface) entry point for the Django application.
# It enables traditional synchronous web servers like Gunicorn or Apache to communicate with Django’s HTTP layer.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()
