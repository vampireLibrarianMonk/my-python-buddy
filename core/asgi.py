# Native
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

# Django
from django.core.asgi import get_asgi_application

# Routing
import core.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Create the Asynchronous Server Gateway Interface (ASGI) application
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        # Handle traditional HTTP requests
        "http": django_asgi_app,
        # Handle WebSocket connections
        "websocket": AuthMiddlewareStack(
            URLRouter(core.routing.websocket_urlpatterns),
        ),
    },
)
