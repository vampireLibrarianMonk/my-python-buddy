# Django
from django.urls import re_path

# Consumer
from core import consumers

# WebSocket route for analyzers
websocket_urlpatterns = [
    re_path(r"ws/analyzer/(?P<sha256>\w+)/$", consumers.AnalyzerConsumer.as_asgi()),
]
