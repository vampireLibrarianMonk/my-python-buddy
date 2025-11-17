#!/usr/bin/env python
# coding: utf-8

# # Note it was found that I could not easily dynamically pull the notebook name so if you update the notebook update the following code:

# In[1]:


# Run the following once and once only when setting up jupyter notebooks for the 13-XX-XX series tests. Comment out afterwards.
# sudo apt install -y python3-dmidecode

# The following has to be done to ensure you are using the NVIDIA GPU.
# Be in base repo directory
# wget https://developer.download.nvidia.com/compute/cuda/12.4.1/local_installers/cuda_12.4.1_550.54.15_linux.run
# sudo sh cuda_12.4.1_550.54.15_linux.run
#
# conda env create -f environment.yml
#
# CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python
#
# export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH
#
# Test via:
# python -c "from llama_cpp import Llama; Llama(model_path='{FULL_MODEL_PATH_HERE}', n_gpu_layers=1, verbose=True)" 2>&1 | grep "Device"
#
# Example Output:
# Device 0: NVIDIA GeForce RTX 3090, compute capability 8.6, VMM: yes


# In[2]:


nb_name = "MAT-13-01-level-1-notebook"


# In[3]:


import os
import subprocess
import sys
import time
from datetime import datetime
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


# In[4]:


from llama_cpp import Llama
from views_chat_utilities import get_cleaned_code_response

# In[5]:


# Load local fine-tuned model (GGUF) once at startup
model_name = "llama-2-7b-143k-codeAlpaca-q4_K_M-2025-10-30_1326.gguf"
full_model_path = os.path.join(base_dir, "models", model_name)
llm = Llama(
    model_path=os.path.join(base_dir, "models", model_name),
    n_ctx=4096,  # expand to match the model’s training context
    n_gpu_layers=-1,  # keep all layers on GPU (auto-fit)
    verbose=False,  # disables most llama.cpp logs
)


# In[6]:


# Check that llama-cpp-python (in notebook) can find the gpu
subprocess.run(
    [
        "bash",
        "-c",
        f"python -c \"from llama_cpp import Llama; Llama(model_path='{full_model_path}', n_gpu_layers=1, verbose=True)\" 2>&1 | grep 'Device'",
    ],
    check=True,
)


# In[7]:


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


# In[8]:


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
        cleaned_response, prompt_tokens, max_new_tokens = get_cleaned_code_response(llm, user_question)
        end_time = time.time()
        duration = end_time - start_time
        execution_times.append(duration)

        #  Display and record results
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
