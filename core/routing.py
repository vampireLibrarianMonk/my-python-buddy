"""
Routing config for core project.

# This file maps WebSocket URL patterns to their corresponding Django Channels consumers.
# It connects specific analyzer sessions, identified by file hash, to their live update streams.

For more information on this file, see
https://channels.readthedocs.io/en/stable/topics/routing.html
"""

# Django
from django.urls import re_path

# Consumer
from core import consumers

# WebSocket route for analyzers
websocket_urlpatterns = [
    re_path(r"ws/analyzer/(?P<sha256>\w+)/$", consumers.AnalyzerConsumer.as_asgi()),
]
