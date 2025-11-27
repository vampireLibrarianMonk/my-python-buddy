# Native
import asyncio
import json
import os

from channels.layers import get_channel_layer

# Channels
from channels.testing import WebsocketCommunicator
from django.core.handlers.wsgi import WSGIHandler

# Django
from django.core.wsgi import get_wsgi_application
from django.test import Client, TestCase

# Core
from core.asgi import application as asgi_app
from core.wsgi import application as wsgi_app


class TestCoreWebSocket(TestCase):
    # Full consumer with websocket functionality test using Channels with ASGI.

    async def _run_full_websocket_flow(self):
        # Test the full websocket round-trip from connection to group broadcast.
        communicator = WebsocketCommunicator(
            asgi_app,
            "/ws/analyzer/test_location/",
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected, "WebSocket failed to connect")

        channel_layer = get_channel_layer()

        # Must match your consumer’s group name exactly:
        await channel_layer.group_send(
            "analyzer_test_location",
            {
                "type": "send_update",
                "data": {"status": "ok"},
            },
        )

        message = await communicator.receive_json_from()
        self.assertEqual(message, {"status": "ok"})

        await communicator.disconnect()

    def test_full_websocket_flow(self):
        """Run the async websocket test inside Django's synchronous runner."""
        asyncio.run(self._run_full_websocket_flow())


class TestAnalyzerConsumer(TestCase):
    # Functional testing of the AnalyzerConsumer via Web Sockets
    # * Connection
    # * Group behavior (add & discard)
    # * Broadcasting
    # * Serialization with JSON
    # * Formation of correct group names

    async def async_test_connect_and_disconnect(self):
        communicator = WebsocketCommunicator(
            asgi_app,
            "/ws/analyzer/test_connection/",
        )

        #  Connect
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Ensure the consumer joined the correct group
        channel_layer = get_channel_layer()
        group_name = "analyzer_test_connection"

        # Here we rely on the upcoming send works since development (in-memory channel layer) groups are not
        # inspectable.

        #  Disconnect
        await communicator.disconnect()

        # After disconnect, group_send should no longer reach the consumer
        await channel_layer.group_send(
            group_name,
            {"type": "send_update", "data": {"msg": "SHOULD_NOT_ARRIVE"}},
        )

        # A deterministic check on post-disconnect behavior
        self.assertTrue(await communicator.receive_nothing())

    async def async_test_send_update(self):
        communicator = WebsocketCommunicator(
            asgi_app,
            "/ws/analyzer/test_connection/",
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        channel_layer = get_channel_layer()
        group_name = "analyzer_test_connection"

        # Send event to the group to consumer.send_update()
        await channel_layer.group_send(
            group_name,
            {
                "type": "send_update",
                "data": {"status": "running", "progress": 55},
            },
        )

        # Expect consumer to send JSON frame back
        response = await communicator.receive_from()
        parsed = json.loads(response)

        self.assertEqual(parsed, {"status": "running", "progress": 55})

        await communicator.disconnect()

    async def async_test_receive_noop(self):
        # Ensure receive() does nothing and does not error out when client sends text_data.
        communicator = WebsocketCommunicator(
            asgi_app,
            "/ws/analyzer/nooptest/",
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Client sends data to the consumer
        await communicator.send_to(text_data="client message")

        # No message expected from consumer
        result = await communicator.receive_nothing()
        self.assertTrue(result)

        await communicator.disconnect()

    # Django entrypoints for async tests
    def test_connect_and_disconnect(self):
        asyncio.run(self.async_test_connect_and_disconnect())

    def test_send_update(self):
        asyncio.run(self.async_test_send_update())

    def test_receive_noop(self):
        asyncio.run(self.async_test_receive_noop())


class TestWSGI(TestCase):
    # Barebones test for wsgi
    # * Environment settings pull
    # * Check instance via import and the factory called
    # * Single valid round-trip request

    def setUp(self):
        # Ensure the environment is set before importing Django
        self.original_settings = os.environ.get("DJANGO_SETTINGS_MODULE")
        os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"

    def tearDown(self):
        if self.original_settings is not None:
            os.environ["DJANGO_SETTINGS_MODULE"] = self.original_settings

    def test_wsgi_application_loads_and_serves(self):
        # Check that we imported a WSGIHandler
        self.assertIsInstance(wsgi_app, WSGIHandler)

        # Verify that calling the factory returns the same type
        fresh_app = get_wsgi_application()
        self.assertIsInstance(fresh_app, WSGIHandler)

        # Perform a simple request round‑trip with the WSGI object directly invoked
        client = Client(handler=fresh_app)
        response = client.get("/", follow=True)
        self.assertEqual(response.status_code, 200)
