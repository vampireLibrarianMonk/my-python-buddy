#!/usr/bin/env python
# coding: utf-8

# # Warning: Due to space constraints from running my tests I clear out the zip and unzipped folders. Ensure you have the zip stored in a separate location for additional operations.
#
# # Note it was found that I could not easily dynamically pull the notebook name so if you update the notebook update the following code:

# In[1]:


# Run the following once and once only when setting up jupyter notebooks for the 12-xx-xx series tests
# sudo apt install -y python3-dmidecode
# !pip3 install torch==2.8.0+cu124 --index-url https://download.pytorch.org/whl/cu124


# In[2]:


nb_name = "MAT-12-03-search-query-notebook"


# In[3]:


# Native
import concurrent.futures
import hashlib
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

# Third Party
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# In[4]:


# Confirm you are using the GPU method
def print_gpu_info():
    print("GPU Characteristics Printout")

    # Is CUDA available?
    print("CUDA available:", torch.cuda.is_available())
    print("Device count:", torch.cuda.device_count())

    if torch.cuda.is_available():
        idx = torch.cuda.current_device()
        print("Current device index:", idx)
        print("Device name:", torch.cuda.get_device_name(idx))
        print("Total memory (GB):", round(torch.cuda.get_device_properties(idx).total_memory / 1e9, 2))
        print("Multiprocessors:", torch.cuda.get_device_properties(idx).multi_processor_count)
        print("Compute capability:", torch.cuda.get_device_properties(idx).major, ".", torch.cuda.get_device_properties(idx).minor)
        print("CUDA Runtime:", torch.version.cuda)


# In[5]:


# Exercise GPU Printout
print_gpu_info()


# In[6]:


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


# In[7]:


from views_chat_utilities import build_summary_prompt, clean_and_build_summary, perform_brave_search_query

# In[8]:


get_ipython().system('django-admin startproject temp_project')


# In[9]:


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


# In[10]:


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
    "discard": ["reddit.com", "stackoverflow.com", "github.com", "gitlab.com", "quora.com", "geeksforgeeks.org"],
}
# Update Django settings dynamically
setattr(settings, "RELEVANT_SECURITY_DOMAINS", RELEVANT_SECURITY_DOMAINS)


# In[21]:


# Generates a cleaned text response using a Hugging Face model pipeline (non-llama specific).
def get_cleaned_summary_response_merged_model(llm_model, tokenizer, user_question):
    # Perform search query and retrieve top snippets
    citation_block, formatted_snippet_block = perform_brave_search_query(user_question)

    # Strong factual summarizer prompt (revised)
    max_new_tokens = 360
    summarize_max_words = max_new_tokens / 4

    system_prompt = build_summary_prompt(user_question, formatted_snippet_block)

    # Build conversation structure
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    # Attempt to build a structured prompt (chat template if available)
    try:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    except Exception:
        bos = tokenizer.bos_token or ""
        prompt = f"{bos}[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{user_question} [/INST]"

    # Configure model for inference
    llm_model.eval()
    try:
        # Some models may not support gradient checkpointing disable
        llm_model.gradient_checkpointing_disable()  # noqa: B110
    except AttributeError:
        # Attribute may not exist on all model types and is safe to ignore
        pass
    llm_model.config.use_cache = True

    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # Generation settings
    max_new_tokens = 300
    generation_kwargs = dict(
        max_new_tokens=max_new_tokens,
        do_sample=False,
        repetition_penalty=1.05,
        no_repeat_ngram_size=6,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.eos_token_id,
        return_full_text=False,
    )

    # print("SYSTEM PROMPT:\n", system_prompt[:500])
    # print("SNIPPET LENGTH:", len(formatted_snippet_block))

    # Create pipeline and generate
    text_pipe = pipeline(
        task="text-generation",
        model=llm_model,
        tokenizer=tokenizer,
        device_map="auto",
    )

    result = text_pipe(prompt, **generation_kwargs)

    # print("RESULT:", result)

    # Extract generated text and token counts
    generated_text = result[0]["generated_text"].strip()
    prompt_tokens = len(tokenizer.encode(prompt))
    max_tokens_used = max_new_tokens

    # Postprocess text (placeholder for cleaning or formatting)
    cleaned_text = clean_and_build_summary(generated_text, citation_block, formatted_snippet_block)

    return cleaned_text, prompt_tokens, max_tokens_used


# In[12]:


# Compute SHA256 of a file
def sha256sum(file_path, block_size=65536):
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            sha.update(chunk)
    return sha.hexdigest()


# In[13]:


# Define paths
zip_path = os.path.join(base_dir, "models", "llama-2-7b-143k-codeAlpaca-2025-10-30_1326.zip")
hash_path = os.path.join(base_dir, "models", "llama-2-merged-7b-143k-codeAlpaca-2025-10-30_1326-hash.txt")
extract_dir = os.path.join(base_dir, "models", "llama-2-merged-7b-14k-codeAlpaca-2025-10-30_1143")


# In[14]:


if os.path.exists(extract_dir):
    try:
        shutil.rmtree(extract_dir)
        print(f"Successfully deleted directory: {extract_dir}")
    except Exception as e:
        print(f"Error deleting {extract_dir}: {e}")
else:
    print(f"Directory not found: {extract_dir}.")


# In[15]:


# Read expected hash
with open(hash_path, "r") as f:
    expected_hash = f.read().strip()

# Compute actual hash
actual_hash = sha256sum(zip_path)

# Compare
if actual_hash == expected_hash:
    print(f"Hash verified: {actual_hash}")
else:
    raise Exception((f"Hash mismatch!\nExpected: {expected_hash}\nFound: {actual_hash}"))


# In[16]:


if not os.path.exists(extract_dir):
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()

        # Define a worker that extracts one file at a time
        def extract_member(member):
            zf.extract(member, extract_dir)

        # Use ThreadPoolExecutor (I/O bound) instead of ProcessPoolExecutor
        # because ZipFile objects aren’t pickle-safe
        with concurrent.futures.ThreadPoolExecutor() as executor:
            list(
                tqdm(
                    executor.map(extract_member, members),
                    total=len(members),
                    desc="Extracting",
                ),
            )
    print(f"Extracted to: {extract_dir}")
else:
    print(f"Directory already exists: {extract_dir}")


# In[17]:


# Remove archive (comment out if you want to keep it)
if os.path.exists(zip_path):
    try:
        os.remove(zip_path)
        print(f"Successfully deleted archive: {zip_path}")
    except Exception as e:
        print(f"Error deleting file {zip_path}: {e}")
else:
    print(f"File not found: {zip_path}")


# In[18]:


# Load model and tokenizer
print("Loading model...")
model = AutoModelForCausalLM.from_pretrained(extract_dir, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(extract_dir)

# Confirm load
print(f"Model and tokenizer loaded from {extract_dir}")


# In[19]:


questions = [
    "What is a secure alternative to the python pickle module?",
    "What are the security implications for the subprocess module?",
    "How should I mitigate 'subprocess call with shell=True identified'?",
    "What is a secure hashing algorithm to use instead of md5?",
    "What are common hardcoded secret patterns detected by Dodgy in Python?",
]


# In[22]:


# Setup output directory and file
base_dir = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
results_dir = base_dir / "test_results"
results_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
output_file = results_dir / f"{nb_name}_{timestamp}.txt"

execution_times = []  # store all durations

# Begin loop over questions
with open(output_file, "w", encoding="utf-8") as f:
    for i, user_question in enumerate(questions, start=1):
        print(f"\nQuestion {i}: {user_question}")
        f.write(f"\nQuestion {i}: {user_question}\n")

        # Measure time
        start_time = time.time()
        cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_summary_response_merged_model(model, tokenizer, user_question)
        end_time = time.time()
        duration = end_time - start_time
        execution_times.append(duration)

        # Display and record results
        print(f"Cleaned Response:\n{cleaned_response}")
        print("-" * 88)

        f.write(f"Cleaned Response:\n{cleaned_response}\n")
        f.write(f"Prompt Tokens: {prompt_tokens}\n")
        f.write(f"Max New Tokens: {max_new_tokens}\n")
        f.write(f"Time Taken: {duration:.2f} seconds\n")
        f.write("Is result correct? If not, one sentence as to why:\n\n")
        f.write("-" * 88 + "\n")

    # Compute and record summary stats
    if execution_times:
        low_time = min(execution_times)
        high_time = max(execution_times)
        avg_time = sum(execution_times) / len(execution_times)

        summary = (
            f"\nExecution Time Summary:\n"
            f"Lowest Time:  {low_time:.2f} seconds\n"
            f"Highest Time: {high_time:.2f} seconds\n"
            f"Average Time: {avg_time:.2f} seconds\n"
        )

        print(summary)
        f.write(summary)

print(f"\nAll results recorded to: {output_file}")


# In[ ]:


# Cleanup extracted directory
try:
    shutil.rmtree(extract_dir)
    print(f"Successfully deleted directory: {extract_dir}")
except Exception as e:
    print(f"Error deleting {extract_dir}: {e}")


# In[ ]:


# Django Cleanup

# Path to your temp project (adjust if needed)
temp_project_path = os.path.join(os.getcwd(), "temp_project")

# Remove the directory and all contents
if os.path.exists(temp_project_path):
    shutil.rmtree(temp_project_path)
    print(f"Removed: {temp_project_path}")
else:
    print("No temp_project folder found.")


# In[ ]:
