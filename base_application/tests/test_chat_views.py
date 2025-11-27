# Native
import json
import os
import re
import subprocess
from pathlib import Path

# Unit Test
from unittest.mock import patch

from django.conf import settings as dj_settings

# Django
from django.test import Client, TestCase, override_settings
from django.urls import reverse

# Base application chat views utilities
from base_application.views_chat_utilities import CODE_TERMS_PATTERN, SECURITY_TERMS_PATTERN

# Base directory grab
base_dir = Path(__file__).resolve().parent.parent.parent

# Load local fine-tuned model (GGUF) once at startup
model_name = dj_settings.GGUF_FILE_NAME
full_model_path = os.path.join(base_dir, "models", model_name)


@override_settings(
    SECURE_SSL_REDIRECT=False,  # prevents 301 errors
)
class ChatCoreTests(TestCase):
    def setUp(self):
        self.client = Client()

    # Pathway helpers to ensure I test the correct paths
    def test_urls(self):
        chat_reset_url = reverse("chat_reset")
        chat_llm_url = reverse("chat_llm")

        # Assert that both reverse paths resolve correctly
        self.assertEqual(chat_reset_url, "/api/chat_reset/")
        self.assertEqual(chat_llm_url, "/api/chat_llm/")

    def test_check_redirect(self):
        # Take out trailing slash
        response = self.client.post("/api/chat_reset", follow=False)

        # Redirect will add slash for 301
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.get("Location"), "/api/chat_reset/")

    # chat_reset pathway
    def test_chat_reset_post(self):
        url = reverse("chat_reset")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "reset"})

    def test_chat_reset_not_post(self):
        url = reverse("chat_reset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    # chat_llm exception handling check
    def test_chat_llm_missing_prompt(self):
        url = reverse("chat_llm")
        response = self.client.post(
            url,
            data=json.dumps({"prompt": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing prompt", response.content.decode())

    def test_chat_llm_wrong_method(self):
        url = reverse("chat_llm")
        response = self.client.get(url)  # post only not get
        self.assertEqual(response.status_code, 405)

    def test_chat_llm_chat_session_save_failure(self):
        # Force an error with the Chat Session Model
        url = reverse("chat_llm")

        # Patch ChatSession.save to throw an exception
        with patch("base_application.models.ChatSession.save", side_effect=Exception("Simulate Database Error")):
            response = self.client.post(
                url,
                data=json.dumps({"prompt": "Are cucumbers better pickled?"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 500)

            json_response = response.json()

            self.assertIn("ChatSession_creation_fail", json_response)
            self.assertIn("Simulate Database Error", json_response["ChatSession_creation_fail"])

    def test_chat_llm_bad_payload_exception(self):
        # Bad payload simulation
        url = reverse("chat_llm")

        # Send an invalid data type
        response = self.client.post(
            url,
            data="not-a-json",
            content_type="application/json",
        )

        json_response = response.json()

        self.assertEqual(response.status_code, 500)
        self.assertIn("chat_llm_error", json_response)
        self.assertTrue(
            "Expecting value" in json_response["chat_llm_error"] or "Failed to" in json_response["chat_llm_error"],
        )

    def test_chat_inference_gpu_found(self):
        # GPU not CPU inference check (otherwise prompt tests will take much longer)
        try:
            command = (
                'python -c "from llama_cpp import Llama; ' f"Llama(model_path='{full_model_path}', n_gpu_layers=1, verbose=True)\" 2>&1 " '| grep \'Device\''
            )
            result = subprocess.run(
                ["bash", "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            output = result.stdout.strip()

            self.assertIn("Device", output)
            self.assertNotIn("CPU", output)

        except subprocess.CalledProcessError as e:
            self.fail(f"Subprocess failed with error: {e.stderr}")


@override_settings(
    SECURE_SSL_REDIRECT=False,  # prevents 301 errors
)
class ChatCodeTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_chat_llm_code_response(self):
        # Prompt designed to elicit a code response
        url = reverse("chat_llm")
        response = self.client.post(
            url,
            data=json.dumps({"prompt": "Write a Python function to add two numbers."}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        json_response = response.json()

        self.assertIn("response", json_response)
        self.assertTrue("def add_numbers(a, b):\n    return a + b\n" in json_response["response"])

    def test_chat_llm_secure_code_response(self):
        # Split by pipe to get each secure term
        secure_terms = [
            re.sub(r"[^A-Za-z]", "", t.replace("\\w", "").replace("\\d", "").replace("\\s", " ")).strip()
            for t in SECURITY_TERMS_PATTERN.replace("\\b(", "").replace(")\\b", "").split("|")
        ]

        # Split by pipe to get each search term
        search_terms = [t for t in CODE_TERMS_PATTERN.replace("(?<![A-Za-z])(", "").replace(")(?![A-Za-z])", "").split("|")]

        # Get rid of empty element
        search_terms = list(filter(None, search_terms))

        # Iterate over them
        for search_term in search_terms:
            for secure_term in secure_terms:
                # Prompt designed to elicit a response for secure code that is outside the scope of this project
                url = reverse("chat_llm")
                search_sentence = f"{search_term} a {secure_term} way to do a particular task."
                response = self.client.post(
                    url,
                    data=json.dumps({"prompt": search_sentence}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)

                json_response = response.json()

                self.assertIn("response", json_response)
                self.assertTrue(
                    "Please refer to the conversational security assistant for secure guidance." in json_response["response"],
                )


@override_settings(
    SECURE_SSL_REDIRECT=False,  # prevents 301 errors
)
class ChatSearchTests(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(BRAVE_API_KEY=None)
    def test_chat_llm_no_brave_api_key(self):
        # Take out brave search api key to test brave response != 200
        url = reverse("chat_llm")
        response = self.client.post(
            url,
            data=json.dumps({"prompt": "What's up with tomatoes, is it a fruit or a vegetable?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        json_response = response.json()
        self.assertIn("response", json_response)
        self.assertIn("The brave search api has failed.", json_response["response"])

    def test_chat_llm_search_prompt(self):
        # Valid LLM prompt should return a 200 with expected keys
        url = reverse("chat_llm")
        response = self.client.post(
            url,
            data=json.dumps({"prompt": "What is Django?"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        json_response = response.json()

        self.assertIn("response", json_response)
        good_results = (
            "Django" in json_response["response"]
            and "web framework" in json_response["response"]
            and "REST" in json_response["response"]
            and "Python" in json_response["response"]
        )
        self.assertTrue(good_results)
