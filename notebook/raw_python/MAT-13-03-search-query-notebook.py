#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import shutil
import sys
from pathlib import Path

# Get project base directory (one level up from current working directory)
base_dir = Path.cwd().parent

base_application_dir = base_dir / "base_application"

# Convert to absolute string path
base_application_dir = str(base_application_dir.resolve())

# Add to Python path if not already present
if base_application_dir not in sys.path:
    sys.path.append(base_application_dir)

print("base_application added to PATH:")
print(base_application_dir)


# In[2]:


from llama_cpp import Llama
from views_chat_utilities import get_cleaned_summary_response

# In[3]:


# Load local fine-tuned model (GGUF) once at startup
model_name = "llama-2-7b-143k-codeAlpaca-q4_K_M-2025-10-29_1424.gguf"
llm = Llama(
    model_path=os.path.join(base_dir, "models", model_name),
    n_ctx=4096,  # expand to match the model’s training context
    n_gpu_layers=-1,  # keep all layers on GPU (auto-fit)
    verbose=False,  # disables most llama.cpp logs
)


# In[4]:


get_ipython().system('django-admin startproject temp_project')


# In[5]:


import getpass
import os

import django
from django.conf import settings

# Set Django settings module
os.environ["DJANGO_SETTINGS_MODULE"] = "temp_project.temp_project.settings"

# Initialize Django
django.setup()

# Prompt user securely for Brave API key
BRAVE_API_KEY = getpass.getpass("Enter your Brave API key: ")

# Store it as an environment variable
os.environ["BRAVE_API_KEY"] = BRAVE_API_KEY

# Update Django settings dynamically
setattr(settings, "BRAVE_API_KEY", BRAVE_API_KEY)

# Confirm it’s now available
print("Brave API Key loaded successfully.")


# In[6]:


RELEVANT_SECURITY_DOMAINS = {
    "boost": [
        # Manually found good sources
        "arjancodes.com",
        # Core analyzers and secure-coding authorities
        "bandit.readthedocs.io",
        "semgrep.dev",
        "mypy.readthedocs.io",
        "docs.python.org",
        "owasp.org",
        # Reliable security blogs / research
        "snyk.io",
        "securitylab.github.com",
    ],
    "discard": [
        "reddit.com",
        "stackoverflow.com",
        "github.com",
        "gitlab.com",
        "quora.com",
        "geeksforgeeks.org",
    ],
}
# Update Django settings dynamically
setattr(settings, "RELEVANT_SECURITY_DOMAINS", RELEVANT_SECURITY_DOMAINS)


# In[7]:


questions = [
    "What is a secure alternative to the python pickle module?",
    "What are the security implications for the subprocess module?",
    "How should I mitigate 'subprocess call with shell=True identified'?",
    "What is a secure hashing algorithm to use instead of md5?",
    "What are common hardcoded secret patterns detected by Dodgy in Python?",
]


# In[8]:


for i, user_question in enumerate(questions, start=1):
    cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_summary_response(llm, user_question)
    print(f"\nQuestion {i}: {user_question}")
    print(f"Cleaned Response: {cleaned_response}")
    print(f"\n\nPrompt Tokens: {prompt_tokens}")
    print(f"Max New Tokens: {max_new_tokens}")
    print("-" * 88)


# In[9]:


# Django Cleanup

# Path to your temp project (adjust if needed)
temp_project_path = os.path.join(os.getcwd(), "temp_project")

# Remove the directory and all contents
if os.path.exists(temp_project_path):
    shutil.rmtree(temp_project_path)
    print(f"Removed: {temp_project_path}")
else:
    print("No temp_project folder found.")
