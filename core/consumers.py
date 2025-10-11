# Native
import json

# Redis
from channels.generic.websocket import AsyncWebsocketConsumer


class AnalyzerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.sha256 = self.scope["url_route"]["kwargs"]["sha256"]
        self.group_name = f"analyzer_{self.sha256}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # clients don't send

    async def send_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
