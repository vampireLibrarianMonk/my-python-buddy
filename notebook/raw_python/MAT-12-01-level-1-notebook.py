#!/usr/bin/env python
# coding: utf-8

# In[1]:


# sudo apt install python3-dmidecode
# !pip3 install torch==2.8.0+cu126 --index-url https://download.pytorch.org/whl/cu126
# !pip3 install tqdm


# In[2]:


# Native
import concurrent.futures
import hashlib
import os
import shutil
import sys
import zipfile
from pathlib import Path

from tqdm import tqdm

# Third Party
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# In[3]:


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


# In[14]:


from views_chat_utilities import SYSTEM_PROMPTS

# In[16]:


# Generates a cleaned text response using a Hugging Face model pipeline (non-llama specific).
def get_cleaned_code_response_merged_model(llm_model, tokenizer, user_question):
    # Normalize system prompt
    system_prompt = SYSTEM_PROMPTS["code_writer"]

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

    # Create pipeline and generate
    text_pipe = pipeline(
        task="text-generation",
        model=llm_model,
        tokenizer=tokenizer,
        device_map="auto",
    )

    result = text_pipe(prompt, **generation_kwargs)

    # Extract generated text and token counts
    generated_text = result[0]["generated_text"].strip()
    prompt_tokens = len(tokenizer.encode(prompt))
    max_tokens_used = max_new_tokens

    # Postprocess text (placeholder for cleaning or formatting)
    cleaned_text = generated_text.strip()

    return cleaned_text, prompt_tokens, max_tokens_used


# In[5]:


# Compute SHA256 of a file
def sha256sum(file_path, block_size=65536):
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            sha.update(chunk)
    return sha.hexdigest()


# In[6]:


# Define paths
zip_path = os.path.join(base_dir, "models", "llama-2-7b-143k-codeAlpaca-2025-10-30_1326.zip")
hash_path = os.path.join(base_dir, "models", "llama-2-merged-7b-143k-codeAlpaca-2025-10-30_1326-hash.txt")
extract_dir = os.path.join(base_dir, "models", "llama-2-merged-7b-14k-codeAlpaca-2025-10-30_1143")


# In[7]:


if os.path.exists(extract_dir):
    try:
        shutil.rmtree(extract_dir)
        print(f"Successfully deleted directory: {extract_dir}")
    except Exception as e:
        print(f"Error deleting {extract_dir}: {e}")
else:
    print(f"Directory not found: {extract_dir}.")


# In[8]:


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


# In[9]:


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


# In[10]:


# Remove archive (comment out if you want to keep it)
if os.path.exists(zip_path):
    try:
        os.remove(zip_path)
        print(f"Successfully deleted archive: {zip_path}")
    except Exception as e:
        print(f"Error deleting file {zip_path}: {e}")
else:
    print(f"File not found: {zip_path}")


# In[11]:


# Load model and tokenizer
print("Loading model...")
model = AutoModelForCausalLM.from_pretrained(extract_dir, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(extract_dir)

# Confirm load
print(f"Model and tokenizer loaded from {extract_dir}")


# In[12]:


questions = [
    "Code: How do I reverse a list in Python?",
    "Code: How do I reverse an array in Python?",
    "Code: How do I sort a list of numbers in Python?",
    "Code: How do I remove duplicates from a list in Python?",
    "Code: How do I find the length of a string in Python?",
    "Code: How do I check if a number is even in Python?",
    "Code: How do I concatenate two strings in Python?",
    "Code: How do I get both the index and value while looping through a list in Python?",
    "Code: How do I check if a key exists in a dictionary in Python?",
    "Code: How do I swap the values of two variables without using a third variable in Python?",
]


# In[18]:


for i, user_question in enumerate(questions, start=1):
    cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_code_response_merged_model(model, tokenizer, user_question)

    print(f"\nQuestion {i}: {user_question}")
    print(f"Cleaned Response:\n{cleaned_response}")
    print(f"Prompt Tokens: {prompt_tokens}")
    print(f"Max New Tokens: {max_new_tokens}")
    print("-" * 88)


# In[ ]:


# Cleanup extracted directory
try:
    shutil.rmtree(extract_dir)
    print(f"Successfully deleted directory: {extract_dir}")
except Exception as e:
    print(f"Error deleting {extract_dir}: {e}")
