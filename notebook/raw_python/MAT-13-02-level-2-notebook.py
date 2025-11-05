#!/usr/bin/env python
# coding: utf-8

# In[8]:


import os
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


# In[9]:


from llama_cpp import Llama
from views_chat_utilities import (
    get_cleaned_code_response,
)

# In[10]:


# Load local fine-tuned model (GGUF) once at startup
model_name = "llama-2-7b-143k-codeAlpaca-q4_K_M-2025-10-29_1424.gguf"
llm = Llama(
    model_path=os.path.join(base_dir, "models", model_name),
    n_ctx=4096,  # expand to match the model’s training context
    n_gpu_layers=-1,  # keep all layers on GPU (auto-fit)
    verbose=False,  # disables most llama.cpp logs
)


# In[11]:


questions = [
    "Code: How do I filter even numbers from a list using a list comprehension?",
    "Code: How do I find the common elements between two lists in Python?",
    "Code: How do I remove all vowels from a string in Python?",
    "Code: How do I count how many times each word appears in a string?",
    "Code: How do I check if a string is a palindrome, ignoring case and spaces?",
    "Code: How do I get the current date and time in Python?",
    "Code: How do I find the factorial of a number using recursion in Python?",
    "Code: How do I merge two dictionaries into one in Python?",
    "Code: How do I find all unique words in a sentence, ignoring case and punctuation?",
    "Code: How do I find the most frequent element in a list without using the collections module?",
    "Code: How do I determine if two strings are anagrams of each other in Python?",
]


# In[12]:


for i, user_question in enumerate(questions, start=1):
    cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_code_response(llm, user_question)
    print(f"\nQuestion {i}: {user_question}")
    print(f"Cleaned Response: {cleaned_response}")
    print(f"Prompt Tokens: {prompt_tokens}")
    print(f"Max New Tokens: {max_new_tokens}")
    print("-" * 88)


# In[ ]:
