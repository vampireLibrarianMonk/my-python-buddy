# LLM Chat Bot for Analyzer Context

# Native
import json
import os
import re
from pathlib import Path

from django.conf import settings as dj_settings

# Django
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Llama-cpp-python
# Ensure you have builder libraries installed (sudo apt install build-essential cmake -y).
from llama_cpp import Llama

# Models
from base_application.models import ChatSession, Run
from base_application.views_chat_utilities import (
    SECURITY_TERMS_PATTERN,
    get_cleaned_code_response,
    get_cleaned_summary_response,
)

# Base directory grab
base_dir = Path(__file__).resolve().parent.parent

# Load local fine-tuned model (GGUF) once at startup
model_name = dj_settings.GGUF_FILE_NAME
llm = Llama(
    model_path=os.path.join(base_dir, "models", model_name),
    n_ctx=4096,  # expand to match the model’s training context
    n_gpu_layers=-1,  # keep all layers on GPU (auto-fit)
    verbose=False,  # disables most llama.cpp logs
)

# The following has to be done to ensure you are using the NVIDIA GPU.
# be in base repo directory
# wget https://developer.download.nvidia.com/compute/cuda/12.4.1/local_installers/cuda_12.4.1_550.54.15_linux.run
# sudo sh cuda_12.4.1_550.54.15_linux.run
# conda env create -f environment.yml
# CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
# export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH
# Test via:
# python -c "from llama_cpp import Llama; Llama(model_path='', n_gpu_layers=1, verbose=True)" 2>&1 | grep "Device"
# Example Output:
# Device 0: NVIDIA GeForce RTX 3090, compute capability 8.6, VMM: yes
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
        print("Incoming chat_llm request received.")

        # Retrieve data payload
        data = json.loads(request.body)

        # Security gate for code writing
        user_question = data.get("prompt", "").strip()

        # Missing user prompt validation
        if not user_question:
            return JsonResponse({"error": "Missing prompt"}, status=400)

        # Detect conversational intent (Pathway 1)
        # Written this way in case I want to have more flexibility
        is_search = not re.search(
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

        if not is_search:
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

        # Create ChatSession model record
        try:
            # Retrieve run record
            run_id = data.get("run_id")
            run = Run.objects.filter(id=run_id).first() if run_id else None

            # Clean creation of object
            ChatSession.objects.create(
                run=run,
                file_name=run.submitted_file.original_name if run else "",
                file_hash=run.submitted_file.sha256 if run else "",
                analyzer=run.analyzer if run else data.get("analyzer", ""),
                analyzer_version=getattr(run, "analyzer_version", ""),
                prompt=user_question,
                response=cleaned_response,
                chat_type="search" if is_search else "code",
            )
        except Exception as log_err:
            print(f"Failed to record ChatSession: {log_err}")

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
        print(f"Unhandled exception in chat_llm: {e}")
        return JsonResponse({"error": str(e)}, status=500)
