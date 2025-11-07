# LLM Chat Bot for Analyzer Context

# Native
import json
import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from django.http import JsonResponse

# Django
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

# Llama-cpp-python
# Ensure you have builder libraries installed (sudo apt install build-essential cmake -y).
from llama_cpp import Llama

# Models
from base_application.models import Run
from base_application.views_chat_utilities import (
    SECURITY_TERMS_PATTERN,
    get_cleaned_code_response,
    get_cleaned_summary_response,
)

# Base directory grab
base_dir = Path(__file__).resolve().parent.parent

# Create logs directory
logs_dir = Path(__file__).resolve().parent.parent / "logs"
os.makedirs(logs_dir, exist_ok=True)

# Log file base name (the handler will add timestamps automatically)
log_filename = logs_dir / "chat.log"

# Create a timed rotating file handler (rotates daily, keeps 7 days)
file_handler = TimedRotatingFileHandler(
    filename=log_filename,
    when="midnight",  # Rotate at midnight
    interval=1,  # Every 1 day
    backupCount=7,  # Keep 7 days of logs
    encoding="utf-8",
)

# Formatter for all log outputs
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(formatter)

# Optional: also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

logger.info("Timed rotating logging initialized.")

# Load local fine-tuned model (GGUF) once at startup
model_name = "llama-2-7b-143k-codeAlpaca-q4_K_M-2025-10-29_1424.gguf"
llm = Llama(
    model_path=os.path.join(base_dir, "models", model_name),
    n_ctx=4096,  # expand to match the model’s training context
    n_gpu_layers=-1,  # keep all layers on GPU (auto-fit)
    verbose=False,  # disables most llama.cpp logs
)

# The following has to be done to ensure you are using the NVIDIA GPU.
# pip install llama-cpp-python \
#   --upgrade \
#   --force-reinstall \
#   --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
# export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH
#
# Model Test
# python - <<'PY'
# from llama_cpp import Llama
# llm = Llama(model_path="models/model-q4_k_m.gguf", n_gpu_layers=-1)
# print(llm("Hello world, tell me a short story about GPUs.", max_tokens=50))
# PY
#
# Context Window Size
# python - <<'PY'
# from llama_cpp import Llama
# llm = Llama(model_path="models/model-q4_k_m.gguf")
# print(llm.metadata.get("llama.context_length"))
# PY


def clean_chat_text(text: str, e_map: dict) -> str:
    """
    Cleans user or assistant text before including it in the context window.
    Removes emojis (from e_map and user interface markers), trims extra spaces and
    normalizes line breaks.
    :param text: Text string to clean
    :param e_map: Emoji Map
    :return: cleaned string
    """
    if not text:
        return ""

    # Remove emoji characters defined in the emoji map
    emoji_pattern = "[" + "".join(re.escape(e) for e in e_map.values()) + "]"
    text = re.sub(emoji_pattern, "", text)

    # Remove common UI emojis (user, assistant, warning, bubble)
    ui_emojis = r"[🧑🤖⚠️💬]"
    text = re.sub(ui_emojis, "", text)

    # Normalize whitespace and line breaks
    text = re.sub(r"\s{2,}", " ", text.strip())
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()


# Load and return the source code tied to a run.
def get_code_context(data):
    run_id = data.get("run_id")

    if run_id:
        run = get_object_or_404(Run, id=run_id)
    else:
        raise Exception("No run id found.")

    try:
        # Read code file safely.
        code_path = run.submitted_file.file.path
        with open(code_path, "r", encoding="utf-8", errors="ignore") as f:
            code_text = f.read()

        # Wrap code content in start/end markers.
        lines = code_text.splitlines()
        limited_code = "\n".join(lines)
        code_context = f"=== Code Start ===\n" f"{limited_code.strip()}\n" f"=== Code End ==="

    except Exception as e:
        # Gracefully handle missing or unreadable files.
        code_context = f"=== Code Start ===\n" f"(Could not load source code: {str(e)})\n" f"=== Code End ==="

    return code_context


@csrf_exempt
def chat_reset(request):
    """
    Reset the user's chat session memory.
    Called by frontend on page reload to start a fresh conversation.
    """
    if request.method == "POST":
        request.session["chat_history"] = []
        request.session.modified = True
        return JsonResponse({"status": "reset"})
    return JsonResponse({"error": "POST required"}, status=405)


# Chat Endpoint
@csrf_exempt
def chat_llm(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        logger.info("Incoming chat_llm request received.")

        # Retrieve data payload
        data = json.loads(request.body)

        # Security gate for code writing
        user_question = data.get("prompt", "").strip()

        # Missing user prompt validation
        if not user_question:
            return JsonResponse({"error": "Missing prompt"}, status=400)

        # Detect conversational intent (Pathway 1)
        # Written this way in case I want to have more flexibility
        is_conversational = not re.search(
            r"\b("
            r"code|implement|program|write|rework|"
            r"script|function|class|snippet|example|"
            r"generate|create|refactor|debug|fix|"
            r"build|develop|return|show.*code|"
            r"output.*code|produce.*code"
            r")\b",
            user_question,
            re.IGNORECASE,
        )

        if not is_conversational:
            # If the coding request mentions security topics, do not produce code
            if re.search(SECURITY_TERMS_PATTERN, user_question, re.IGNORECASE):
                return JsonResponse(
                    {
                        "response": "Please refer to the conversational security assistant for secure guidance.",
                    },
                    status=200,
                )
            else:
                cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_code_response(llm, user_question)
        else:
            # Get cleaned response from summary prompt to llm
            cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_summary_response(llm, user_question)

        # Get LLM context window
        context_window = getattr(llm, "n_ctx", lambda: 4096)()

        #  Automatic reset when context full
        remaining_tokens = max(0, context_window - prompt_tokens)

        return JsonResponse(
            {
                "response": cleaned_response,
                "usage": {
                    "context_window": context_window,
                    "prompt_tokens": prompt_tokens,
                    "remaining_tokens": remaining_tokens,
                    "max_new_tokens": max_new_tokens,
                },
            },
        )

    except Exception as e:
        logger.exception(f"Unhandled exception in chat_llm: {e}")
        return JsonResponse({"error": str(e)}, status=500)
