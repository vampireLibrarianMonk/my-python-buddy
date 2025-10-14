"""
Consumer config for core project.

# This file defines the WebSocket consumer responsible for real-time analyzer updates in Django Channels.
# It manages client connections, group messaging and streaming of analyzer status or findings to the browser.

For more information on this file, see
https://channels.readthedocs.io/en/stable/topics/consumers.html
"""

# Native
import json

# Redis
from channels.generic.websocket import AsyncWebsocketConsumer


class AnalyzerConsumer(AsyncWebsocketConsumer):
    # Establish websocket connection and join analyzer group
    async def connect(self):
        self.sha256 = self.scope["url_route"]["kwargs"]["sha256"]
        self.group_name = f"analyzer_{self.sha256}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    # Cleanly remove connection from analyzer group
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Placeholder for client messages (none expected)
    async def receive(self, text_data):
        pass  # clients don't send

    # Broadcast analyzer updates to connected websocket clients
    async def send_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
