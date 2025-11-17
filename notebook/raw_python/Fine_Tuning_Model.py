#!/usr/bin/env python
# coding: utf-8

# # 1. Prime library install

# In[1]:


# Check python version
get_ipython().system('python3 --version')


# In[2]:


get_ipython().system('pip install accelerate==1.10.0')
get_ipython().system('pip install datasets==4.0.0')
get_ipython().system('pip install peft==0.17.0')
get_ipython().system('pip install transformers==4.55.2')
get_ipython().system('pip install trl==0.21.0')
get_ipython().system('pip install mistral-common==1.3.4')


# # 2. Prime Library Version Print

# In[3]:


import accelerate
import datasets
import mistral_common
import peft
import transformers
import trl

print("Library Versions:")
print(f"accelerate     : {accelerate.__version__}")
print(f"datasets       : {datasets.__version__}")
print(f"peft           : {peft.__version__}")
print(f"transformers   : {transformers.__version__}")
print(f"trl            : {trl.__version__}")
print(f"mistral-common : {mistral_common.__version__}")


# In[4]:


get_ipython().system('pip3 install torch==2.8.0+cu126 --index-url https://download.pytorch.org/whl/cu126')


# In[5]:


# Verify PyTorch and CUDA versions for compatibility with the training setup.
# Used in latest run.
# PyTorch 2.8.0+cu126 built against CUDA 12.6.
# NVIDIA A100 (Driver 550.54.15, CUDA 12.4 runtime).
import torch

print("PyTorch Version:", torch.__version__)
print("CUDA Version:", torch.version.cuda)


# # 3. GPU Hardware and CUDA Check

# In[6]:


# Check the number of GPUs available
num_gpus = torch.cuda.device_count()
print(f"Number of GPUs available: {num_gpus}")


# In[7]:


get_ipython().system('nvidia-smi')


# # 4. Import the libraries and modules used for fine-tuning a large language model (LLM).

# In[8]:


# Securely prompt for the API key without showing it in the terminal
import getpass

# Hashing of models for download verification
import hashlib

# Structure text operations
import json

# Access OS utilities, system commands and process management tools
import os
import shutil
import subprocess
import sys

# Date time from system
from datetime import datetime

# Compute perplexity from evaluation loss
from math import exp

# Work with filesystem paths in a cross-platform, object-oriented way
from pathlib import Path

# Web based actions library
import requests

# Hugging face dataseets library
from datasets import load_dataset

# Google drive mounting capability
from google.colab import drive

# Import login utility to authenticate with the Hugging Face Hub
from huggingface_hub import login

# Parameter-Efficient Fine-Tuning (PEFT)
# Give the ability to adapt LLMs without having to redo all the weights.
# Utilizes Low-Rank Adapter (LoRA).
# Efficiently fine-tune without redoing all their parameters.
# Overall reduces compute cost while preserving performance of the model.
from peft import LoraConfig, PeftModel, get_peft_model

# Import Hugging Face pipeline for streamlined text generation tasks
# Import model and tokenizer classes for causal language modeling
# Define and manage training configuration settings (e.g., epochs, batch size, learning rate)
# Import model, tokenizer, and training utilities from the Transformers library
from transformers import AutoModelForCausalLM  # Loads a causal language model (e.g., Llama)
from transformers import AutoTokenizer  # Handles text tokenization for the model
from transformers import HfArgumentParser  # Parses command-line or script arguments
from transformers import TrainingArguments  # Defines training configurations and hyperparameters
from transformers import logging  # Controls logging verbosity and output
from transformers import pipeline  # Creates ready-to-use NLP pipelines for inference

# Transformers Reinforcement Learning (TRL)
# Supervised Fine-Tuning (SFT)
# Import the SFTTrainer to manage supervised fine-tuning
from trl import SFTTrainer

# # 5. Miscellaneous Methods Declaration

# In[9]:


# Compute SHA-256 hash of the zip.
def compute_sha256(file_path, block_size=65536):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# # 6. Mount Google Drive

# In[10]:


drive.mount("/content/drive", force_remount=True)

# Define base save directory
drive_save_dir = "/content/drive/MyDrive/models"
os.makedirs(drive_save_dir, exist_ok=True)


# # 7. Time Stamping

# In[11]:


timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")


# # 8. Environment Variables

# In[12]:


# If your notebook sometimes hides devices, force the first GPU visible:
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# Disable Weights & Biases tracking to prevent automatic logging
os.environ["WANDB_DISABLED"] = "true"

# Diagnostics for invalid arguments in transformers pipeline
os.environ["TRANSFORMERS_VERBOSITY"] = "info"

# Output GOOGLE DRIVE path
os.environ["GOOGLE_MODEL_PATH"] = drive_save_dir


# # 9. Hugging Face Authentication

# In[13]:


# Prompt the user to enter their Hugging Face API key securely (hidden input)
hugging_face_key = getpass.getpass("Enter your Hugging Face token: ")

# Log in to Hugging Face Hub using the entered key
login(hugging_face_key)


# # 10. Dataset for fine-tuning

# In[14]:


# set choice either for 14k or 143k
dataset_choice = "14k"


# In[15]:


# Dataset for fine-tuning
if dataset_choice == "14k":
    dataset_name = "nikhiljatiwal/minipython-Alpaca-14k"
elif dataset_choice == "143k":
    dataset_name = "nikhiljatiwal/Llama-2-Python-Alpaca-143k"
else:
    raise Exception("You need to choice a valid data set.")

dataset = load_dataset(dataset_name)

# Get the dataset structure and size
print(dataset)


# # 11. Model input and output config.

# In[16]:


model_choice = "7b"


# In[17]:


# Hugging Face model to train
if model_choice == "7b":
    model_name = "NousResearch/llama-2-7b-chat-hf"
elif model_choice == "13b":
    model_name = "NousResearch/Llama-2-13b-chat-hf"
else:
    raise Exception("You need to choice a valid model.")

# Output model name
new_model = f"/kaggle/working/{model_choice}-{dataset_choice}-codeAlpaca"


# # 12. Quantized + LoRA = QLoRA which is a method of fine-tuning LLMs more cheaply and efficiently without sacrificing accuracy.

# In[18]:


# LoRA attention dimension (rank)
# The higher the value the more fine-grained updates at the cost of increased
# memory usage
lora_r = 64

# LoRA alpha (scaling factor)
# How much the LoRA layes change the original LLM's behavior.
# Higher value = updates stronger : Lower value = keeps changes smaller.
lora_alpha = 16

# LoRA dropout probability
# Randomly turns off some connections during training to avoid overfitting.
lora_dropout = 0.1


# # 13. Training Arguments parameters

# In[19]:


# Output directory where the model predictions and checkpoints will be stored
model_output_dir = f"/kaggle/working/{model_choice}-{dataset_choice}-codeAlpaca"

# Export to environment variable
os.environ["MODEL_OUTPUT_DIR"] = model_output_dir

# Number of training epochs
num_train_epochs = 1

# Enable fp16 training (set to True for mixed precision training)
fp16 = True

# Batch size per GPU for training
per_device_train_batch_size = 8

# Batch size per GPU for evaluation
per_device_eval_batch_size = 8

# Number of update steps to accumulate the gradients for
gradient_accumulation_steps = 2

# Enable gradient checkpointing
gradient_checkpointing = True

# Maximum gradient norm (gradient clipping)
max_grad_norm = 0.3

# Initial learning rate (AdamW optimizer)
learning_rate = 2e-4

# Weight decay to apply to all layers except bias/LayerNorm weights
weight_decay = 0.001

# Optimizer to use
optim = "adamw_torch"

# Learning rate schedule
lr_scheduler_type = "constant"

# Group sequences into batches with the same length
# Saves memory and speeds up training considerably
group_by_length = True

# Ratio of steps for a linear warmup
warmup_ratio = 0.03

# Log every X updates steps
logging_steps = 50


# # 14. Supervised Fine-Tuning (SFT) Model and Tokenizer Setup

# In[20]:


# Set max token length for each training example
max_seq_length = None

# Combine shorter samples for faster training
packing = False

# Load the training dataset
dataset = load_dataset(dataset_name, split="train")

# Load and configure the tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# Load the base model in 8-bit precision for memory efficiency
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto",
)

# Enable gradient checkpointing and input gradients for fine-tuning
model.gradient_checkpointing_enable()
model.enable_input_require_grads()


# # 15. LoRA Configuration, Dataset Tokenization and Trainer Initialization

# In[21]:


# Configure and apply LoRA to the base model
peft_config = LoraConfig(
    r=lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=lora_dropout,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, peft_config)

# Define training arguments
training_arguments = TrainingArguments(
    output_dir=model_output_dir,
    num_train_epochs=num_train_epochs,
    per_device_train_batch_size=per_device_train_batch_size,
    gradient_accumulation_steps=gradient_accumulation_steps,
    learning_rate=learning_rate,
    weight_decay=weight_decay,
    max_grad_norm=max_grad_norm,
    warmup_ratio=warmup_ratio,
    lr_scheduler_type=lr_scheduler_type,
    optim=optim,
    logging_steps=logging_steps,
    fp16=fp16,
    group_by_length=True,
)


# Tokenize dataset and add padding for consistent lengths.
def tokenize_function(example):
    return tokenizer(
        example["text"],
        truncation=True,
        padding="max_length",
        max_length=512,  # limit sequence length
    )


# Split dataset into train and eval sets (e.g., 90/10)
split_dataset = dataset.train_test_split(test_size=0.1, seed=42)  # answer to everything is 42

train_dataset = split_dataset["train"]
eval_dataset = split_dataset["test"]

# Tokenize both
tokenized_train = train_dataset.map(tokenize_function, batched=True)
tokenized_eval = eval_dataset.map(tokenize_function, batched=True)

# Initialize trainer with both datasets
trainer = SFTTrainer(
    model=model,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_eval,
    args=training_arguments,
)


# # 16. Upload SFTTrainer Characteristics to Google Drive
#

# In[22]:


# Declare merged model directory location
merged_model_directory = f"/kaggle/working/llama-2-{model_choice}-{dataset_choice}-codeAlpaca-merged"
os.makedirs(merged_model_directory, exist_ok=True)

# Base directory where your merged model is saved
train_log_dir = merged_model_directory


# Helper: safely convert non-serializable objects
def safe_serialize(obj):
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


# Try to get GPU device info if CUDA is available
if torch.cuda.is_available():
    device_count = torch.cuda.device_count()
    gpu_names = [torch.cuda.get_device_name(i) for i in range(device_count)]
    current_gpu = torch.cuda.get_device_name(torch.cuda.current_device())
else:
    device_count = 0
    gpu_names = []
    current_gpu = "CPU"

# Collect core trainer characteristics
trainer_info = {
    "timestamp": timestamp,
    "model_name": str(model_name),
    "dataset_choice": str(dataset_choice),
    "lora_model": str(new_model),
    "num_train_epochs": trainer.args.num_train_epochs,
    "train_batch_size": trainer.args.per_device_train_batch_size,
    "gradient_accumulation_steps": trainer.args.gradient_accumulation_steps,
    "learning_rate": trainer.args.learning_rate,
    "warmup_steps": getattr(trainer.args, "warmup_steps", None),
    "warmup_ratio": getattr(trainer.args, "warmup_ratio", None),
    "weight_decay": trainer.args.weight_decay,
    "lr_scheduler_type": str(trainer.args.lr_scheduler_type),
    "fp16": bool(getattr(trainer.args, "fp16", False)),
    "bf16": bool(getattr(trainer.args, "bf16", False)),
    "gpu_names": gpu_names,
    "active_gpu": current_gpu,
    "train_runtime": safe_serialize(getattr(trainer.state, "train_runtime", None)),
    "train_loss": safe_serialize(getattr(trainer.state, "log_history", [])[-1].get("loss", None) if trainer.state.log_history else None),
    "final_eval_metrics": safe_serialize(getattr(trainer.state, "log_history", [])[-1] if trainer.state.log_history else None),
}

# Save as JSON file in the same directory as merged model
trainer_info_path = os.path.join(train_log_dir, "trainer_info.json")
with open(trainer_info_path, "w") as f:
    json.dump(trainer_info, f, indent=4)

print("Trainer Characteristics: ")
print(trainer_info_path)

print(f"[INFO] Trainer characteristics saved to {trainer_info_path}")


# In[23]:


# Copy SFTTrainer characteristics json to Google Drive
drive_trainer_path = os.path.join(drive_save_dir, f"llama-2-{model_choice}-{dataset_choice}-codeAlpaca-merged.json")
shutil.copy(trainer_info_path, drive_trainer_path)

print(f"[INFO] SFTTrainer characteristics json uploaded to Google Drive: {drive_trainer_path}")


# # 17. Model Training

# In[24]:


# Train model
trainer.train()

# Save trained model
trainer.model.save_pretrained(new_model)


# # 18. Evaluation of the training regime

# In[25]:


# Base save directory in Google Drive
eval_directory = os.path.join(drive_save_dir, "evaluation_results")
os.makedirs(eval_directory, exist_ok=True)

print("\n[INFO] Starting model evaluation...")

# Evaluate the fine-tuned model
eval_results = trainer.evaluate()

# Compute Perplexity (language-model quality indicator)
try:
    perplexity = exp(eval_results["eval_loss"])
except OverflowError:
    perplexity = float("inf")

# Build evaluation summary text
eval_summary = [
    "--- Evaluation Results ---",
    f"Timestamp: {timestamp}",
]
for k, v in eval_results.items():
    eval_summary.append(f"{k}: {v:.4f}")
eval_summary.append(f"perplexity: {perplexity:.4f}")
summary_text = "\n".join(eval_summary)

# Define evaluation file path inside Google Drive
eval_filename = f"evaluation_llama_{model_choice}_{dataset_choice}_{timestamp}.txt"
drive_eval_path = os.path.join(eval_directory, eval_filename)

# Save metrics to Drive
with open(drive_eval_path, "w") as f:
    f.write(summary_text)

print("\n[INFO] Evaluation complete.")
print(f"[INFO] Results saved to Google Drive: {drive_eval_path}")

# Display metrics in notebook
print("\n" + summary_text)


# # 19. Generate and Display Model Response with Chat Prompt

# In[26]:


# Import text generation pipeline
from transformers import pipeline

# Get fine-tuned model from trainer
gen_model = trainer.model
gen_model.eval()

# Disable gradient checkpointing if active
try:
    gen_model.gradient_checkpointing_disable()
except Exception:
    pass

# Enable cache for faster generation
gen_model.config.use_cache = True

# Set tokenizer padding configuration
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# Define user question for model prompt
question = "How can I write a Python program that calculates the mean, standard " "deviation and coefficient of variation of a dataset from a CSV file?"
messages = [
    {"role": "system", "content": "You are a helpful Python tutor."},
    {"role": "user", "content": question},
]

# Build model input prompt safely
try:
    # Use chat template if tokenizer supports it
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
except Exception:
    # Fallback to Llama-style system prompt
    bos = tokenizer.bos_token or ""
    sys_prompt = "You are a helpful Python tutor."
    prompt = f"{bos}[INST] <<SYS>>\n{sys_prompt}\n<</SYS>>\n\n{question} [/INST]"

# Create text generation pipeline
pipe = pipeline(
    task="text-generation",
    model=gen_model,
    tokenizer=tokenizer,
    device_map="auto",
)

# Generate model response text
out = pipe(
    prompt,
    max_new_tokens=300,
    repetition_penalty=1.05,
    no_repeat_ngram_size=6,
    eos_token_id=tokenizer.eos_token_id,
    pad_token_id=tokenizer.eos_token_id,
    return_full_text=False,
)

# Display generated answer
print(out[0]["generated_text"])


# # 20. Load Base Model, Merge LoRA Weights and Prepare Tokenizer

# In[27]:


# Pick a valid device index (default to 0 if there's only one GPU)
num_gpus = torch.cuda.device_count()
device_id = 1 if num_gpus > 1 else 0
device = f"cuda:{device_id}" if torch.cuda.is_available() else "cpu"

# Load the base model
base_model = AutoModelForCausalLM.from_pretrained(
    model_name,
    low_cpu_mem_usage=True,
    return_dict=True,
    torch_dtype=torch.float16,  # so merging is supported
    device_map="auto",  # Let Hugging Face Transformers to place layers
)

# Load the LoRA weights (attach to base)
lora_model = PeftModel.from_pretrained(base_model, new_model)

# IMPORTANT!: Do NOT manually move when using device_map="auto"
# lora_model.to(device)

# Merge the LoRA weights with the base model weights
# Produces a plain AutoModelForCausalLM
merged_model = lora_model.merge_and_unload()

# Export to environment variable
os.environ["MERGED_MODEL_DIRECTORY"] = merged_model_directory

# IMPORTANT!: Only move if you're on CPU-only
# model.to(device)

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"


# # 21. Save Merged Model and Tokenizer (Google Drive)

# In[28]:


# Save the merged model and tokenizer
merged_model.save_pretrained(merged_model_directory)
tokenizer.save_pretrained(merged_model_directory)

# Zip up the contents of the merged model directory
merged_zip_path = f"{merged_model_directory}.zip"
shutil.make_archive(merged_model_directory, "zip", merged_model_directory)

print(f"[INFO] Zipped merged model saved at: {merged_zip_path}")

# Add timestamp to filename
merged_model_archive_name = f"llama-2-{model_choice}-{dataset_choice}-codeAlpaca-{timestamp}.zip"

# Full path inside Google Drive
drive_merged_model_path = os.path.join(drive_save_dir, merged_model_archive_name)

# Copy zipped archive to Google Drive
shutil.copy(merged_zip_path, drive_merged_model_path)

print(f"[INFO] Merged model archive uploaded to Google Drive: {drive_merged_model_path}")


# In[29]:


merged_model_hash = compute_sha256(merged_zip_path)
print(f"[INFO] SHA-256 hash of merged model: {merged_model_hash}")

# Save the hash to a text file
merged_hash_filename = f"llama-2-merged-{model_choice}-{dataset_choice}-codeAlpaca-{timestamp}-hash.txt"
hash_file_path = os.path.join("/content", merged_hash_filename)
with open(hash_file_path, "w") as f:
    f.write(f"{merged_model_hash}\n")

# Full path for the hash file inside Google Drive
drive_merged_hash_path = os.path.join(drive_save_dir, merged_hash_filename)

# Copy the hash file to Google Drive
shutil.copy(hash_file_path, drive_merged_hash_path)

print(f"[INFO] SHA-256 hash uploaded to Google Drive: {drive_merged_hash_path}")


# # 22. Merged Models Test

# In[30]:


# Use merged model for text generation
gen_model = model
gen_model.eval()

# Disable gradient checkpointing for inference
try:
    gen_model.gradient_checkpointing_disable()
except Exception:
    pass

# Enable cache for faster inference
gen_model.config.use_cache = True

# Set tokenizer padding and alignment
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# Define user question and conversation messages
question = "How can I write a Python program that calculates the mean, standard " "deviation and coefficient of variation of a dataset from a CSV file?"
messages = [
    {"role": "system", "content": "You are a helpful Python tutor."},
    {"role": "user", "content": question},
]

# Build model prompt safely and consistently
try:
    # Use tokenizer chat template if available
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
except Exception:
    # Fallback to simple Llama-style instruction prompt
    bos = tokenizer.bos_token or ""
    sys_prompt = "You are a helpful Python tutor."
    prompt = f"{bos}[INST] <<SYS>>\n{sys_prompt}\n<</SYS>>\n\n{question} [/INST]"

# Create generation pipeline for inference
pipe = pipeline(
    task="text-generation",
    model=gen_model,
    tokenizer=tokenizer,
    device_map="auto",
)

# Generate and display model response
out = pipe(
    prompt,
    max_new_tokens=300,
    do_sample=False,
    repetition_penalty=1.05,
    no_repeat_ngram_size=6,
    eos_token_id=tokenizer.eos_token_id,
    pad_token_id=tokenizer.eos_token_id,
    return_full_text=False,
)

# Print generated answer text
print(out[0]["generated_text"])


# # 23. Configure Llama CPP

# In[31]:


REPO = "/content/llama.cpp"
URL = "https://github.com/ggml-org/llama.cpp.git"

if Path(REPO).exists() and (Path(REPO) / ".git").exists():
    try:
        print(f"[INFO] Updating existing llama.cpp repo")
        subprocess.run(["git", "-C", REPO, "fetch", "--depth", "1", "origin", "HEAD"], check=True)
        subprocess.run(["git", "-C", REPO, "reset", "--hard", "FETCH_HEAD"], check=True)
    except subprocess.CalledProcessError:
        print("[WARN] Update failed, recloning repository...")
        subprocess.run(["rm", "-rf", REPO])
        subprocess.run(["git", "clone", "--depth", "1", URL, REPO], check=True)
else:
    print(f"[INFO] Cloning llama.cpp into {REPO}")
    subprocess.run(["git", "clone", "--depth", "1", URL, REPO], check=True)


# # 24. Build Llama-cpp (with all available cores)

# In[32]:


get_ipython().system(
    'apt-get install -y cmake build-essential &&  cd $REPO &&  mkdir -p build &&  cd build &&  cmake .. &&  cmake --build . --config Release -j$(nproc)',
)


# In[33]:


get_ipython().system('ls -l /content/llama.cpp/build/bin | grep llama-quantize # check for quantize binary')


# In[34]:


get_ipython().system('ls -l /content/llama.cpp/ | grep hf | grep gguf # check for gguf converter binary')


# # 25. Export into GGUF using Llama CPP

# In[35]:


get_ipython().system('cd /content/llama.cpp && python3 /content/llama.cpp/convert_hf_to_gguf.py $MERGED_MODEL_DIRECTORY --outfile /content/model-f16.gguf')


# # 26. Quantize and Export the Model and Conversion Metadata

# In[36]:


# This script runs the llama.cpp quantizer to convert a full-precision GGUF model (F16)
# into a smaller quantized version, reducing model size and improving inference speed.
#
# Quantization helps deploy large models on lower-resource hardware by lowering
# weight precision (e.g., from 16-bit floats to 4-bit integers).
#
# Common quantization levels:
# - q8_0    → 8-bit (highest accuracy, largest size)
# - q5_K    → 5-bit hybrid (good balance between size & quality)
# - q4_K_M  → 4-bit modern (fastest with good accuracy)
# - q4_0    → 4-bit legacy (smallest, but least accurate)
#
# q5_K seems to be the more coherent one
# https://symbl.ai/developers/blog/a-guide-to-quantization-in-llms/
# https://www.reddit.com/r/LocalLLaMA/comments/18q5uej/what_quantization_level_do_you_use/
# https://www.reddit.com/r/LocalLLaMA/comments/1efttb1/could_someone_please_explain_the_naming_scheme/

# Quantization chosen
CHOSEN_QUANT = "q5_K"
os.environ["CHOSEN_QUANT"] = CHOSEN_QUANT

# Assemble file name
os.environ["MAIN_FILE_NAME"] = f"llama-2-{model_choice}-{dataset_choice}-codeAlpaca-{timestamp}"

# GGUF file path
GGUF_FILE_PATH = f"/content/model-{CHOSEN_QUANT}.gguf"
os.environ["GGUF_FILE_PATH"] = GGUF_FILE_PATH


# In[37]:


get_ipython().run_cell_magic(
    'bash',
    '',
    '# Paths to the input full-precision model and output quantized model\nF16_GGUF_PATH="/content/model-f16.gguf"\nLOG_FILE="/content/quantization_${MAIN_FILE_NAME}.log"\n\necho "===== LLaMA.cpp Quantization Log =====" | tee "$LOG_FILE"\necho "Timestamp: $(date)" | tee -a "$LOG_FILE"\necho "Input Model: $F16_GGUF_PATH" | tee -a "$LOG_FILE"\necho "Output Model: $GGUF_FILE_PATH" | tee -a "$LOG_FILE"\necho "Quantization Level: $CHOSEN_QUANT" | tee -a "$LOG_FILE"\necho | tee -a "$LOG_FILE"\n\n/content/llama.cpp/build/bin/llama-quantize "$F16_GGUF_PATH" "$GGUF_FILE_PATH" "$CHOSEN_QUANT" 2>&1 | tee -a "$LOG_FILE"\n\necho | tee -a "$LOG_FILE"\necho "Quantization Completed: $(date)" | tee -a "$LOG_FILE"\necho "[INFO] Log written to: $LOG_FILE"\n\n# Copy log file to Google Drive\ncp $LOG_FILE "$GOOGLE_MODEL_PATH/${MAIN_FILE_NAME}.log"\n',
)


# # 27. Hash file of GGUF Model, export to Google Drive

# In[67]:


gguf_model_hash = compute_sha256(GGUF_FILE_PATH)
print(f"[INFO] SHA-256 hash of gguf model: {gguf_model_hash}")

# Save the hash to a text file
gguf_hash_filename = f"llama-2-gguf-{model_choice}-{dataset_choice}-codeAlpaca-{timestamp}-hash.txt"
hash_file_path = os.path.join("/content", gguf_hash_filename)
with open(hash_file_path, "w") as f:
    f.write(f"{gguf_model_hash}\n")

# Full path for the hash file inside Google Drive
drive_gguf_hash_path = os.path.join(drive_save_dir, gguf_hash_filename)

# Copy the hash file to Google Drive
shutil.copy(hash_file_path, drive_gguf_hash_path)

print(f"[INFO] SHA-256 hash uploaded to Google Drive: {drive_gguf_hash_path}")


# # 28. Save model with timestamped name to Google Drive
#

# In[68]:


# Add timestamp and quantization tag to filename
model_base_name = f"llama-2-{model_choice}-{dataset_choice}-codeAlpaca"
new_model_name = f"{model_base_name}-{CHOSEN_QUANT}-{timestamp}.gguf"
new_model_log = f"{model_base_name}-{CHOSEN_QUANT}-{timestamp}.log"
quant_log_file_path = f"/content/quantization_llama-2-{model_choice}-{dataset_choice}-codeAlpaca-{timestamp}.log"

# Full path inside Google Drive
drive_model_path = os.path.join(drive_save_dir, new_model_name)
drive_log_path = os.path.join(drive_save_dir, new_model_log)

# Copy quantized GGUF to Drive
shutil.copy(GGUF_FILE_PATH, drive_model_path)
shutil.copy(quant_log_file_path, drive_log_path)

print(f"[INFO] Model saved to Google Drive: {drive_model_path}")
print(f"[INFO] Quantization log saved to Google Drive: {drive_log_path}")


# In[69]:


# Add timestamp and quantization tag to filename
model_base_name = f"llama-2-{model_choice}-{dataset_choice}-codeAlpaca"
new_model_name = f"{model_base_name}-{CHOSEN_QUANT}-{timestamp}.gguf"
new_model_log = f"{model_base_name}-{CHOSEN_QUANT}-{timestamp}.log"
quant_log_file_path = f"/content/quantization_llama-2-{model_choice}-{dataset_choice}-codeAlpaca-{timestamp}.log"

# Full path inside Google Drive
drive_model_path = os.path.join(drive_save_dir, new_model_name)
drive_log_path = os.path.join(drive_save_dir, new_model_log)

# Copy quantized GGUF to Drive
shutil.copy(GGUF_FILE_PATH, drive_model_path)
shutil.copy(quant_log_file_path, drive_log_path)

print(f"[INFO] Model saved to Google Drive: {drive_model_path}")
print(f"[INFO] Quantization log saved to Google Drive: {drive_log_path}")


# In[69]:


# # 29. User Download (uncomment if desired)

# In[70]:


# # Offer model download in Colab or report file path
# try:
#     from google.colab import files
#     files.download(GGUF_FILE_PATH)
# except Exception:
#     print("[INFO] Non-Colab environment; GGUF at:", GGUF_FILE_PATH)


# # 30. Install, configure and check llama-cpp-python

# In[71]:


# Remove any CPU wheels, install the exact CUDA 12.4 for the upcoming test integration
get_ipython().system(
    'pip -q install -U https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.16-cu124/llama_cpp_python-0.3.16-cp312-cp312-linux_x86_64.whl',
)

# Show GPU and version (for sanity), then hard-restart the Python runtime so the new wheel is actually loaded
import llama_cpp

print("llama-cpp-python:", llama_cpp.__version__)


# In[72]:


# Import llama.cpp core library interface
from llama_cpp import Llama
from llama_cpp import llama_cpp as CLI

# Retrieve system and build information from llama.cpp
info = CLI.llama_print_system_info()

# Decode bytes output if necessary
try:
    info = info.decode()
except Exception:
    pass

# Display detailed llama.cpp build configuration
# Confirm GPU acceleration is enabled:
#   - Look for a "CUDA :" section (indicates CUDA support compiled in)
#   - Ensure your GPU's SM architecture (e.g., A100 is 800) is listed under ARCHS
#   - CPU-only build is indicated by no CUDA or CPU only
print(info)


# # 31. Verify Hash of GGUF and print

# In[73]:


get_ipython().system('ls -l /content/tmp/')


# In[74]:


print("[INFO] Downloading model and hash from Google Drive...")

os.makedirs("/content/tmp", exist_ok=True)
model_path = f"/content/tmp/{timestamp}-gguf-model-to-check.gguf"
hash_path = f"/content/tmp/{timestamp}-gguf-model-hash-to-check.txt"

shutil.copy(drive_model_path, model_path)
shutil.copy(drive_gguf_hash_path, hash_path)

# Verify hash
with open(hash_path, "r") as f:
    expected_hash = f.read().strip().split()[0]

calculated_hash = compute_sha256(model_path)
if calculated_hash != expected_hash:
    raise ValueError(f"[ERROR] Hash mismatch!\nExpected: {expected_hash}\nGot:      {calculated_hash}")
print(f"[INFO] Model hash verified ({calculated_hash[:12]}...)")

# Load metadata only
llm = Llama(model_path=str(model_path), vocab_only=True, verbose=False)

# Print metadata summary
print("[INFO] GGUF Metadata:")
for k, v in llm.metadata.items():
    print(f"{k} = {v}")


# In[75]:


get_ipython().system('ls -l /content/drive/MyDrive/models')


# # 32. Check the quantized GGUF model with a sample prompt:

# In[76]:


# Define assistant role and secure review instructions
system_prompt = (
    "You are a superb Python programmer well versed in secure coding and practices. "
    "Idenify the vulnerabilities and provide concise, production-ready mitigations. "
    "You will utilize secure defaults and ensure minimal use of dependencies."
    "Use minimal code comments."
    "Refrain from providing payloads that exploit vulnerabilities or any step by step process to attack any software. "
    "When asked to rewrite code ensure you preserve functionality where possible."
)

# Vulnerable example demonstrating unsafe pickle deserialization
code_snippet = """import pickle

def load_user_data(serialized_data):
    # Deserializes user data from a byte stream.
    user_data = pickle.loads(serialized_data)
    return user_data

if __name__ == "__main__":
    malicious_input = input("Enter serialized data: ")
    try:
        serialized_data = bytes.fromhex(malicious_input)
        load_user_data(serialized_data)
    except Exception as e:
        print(f"Deserialization failed: {e}")"""

# Instruct LLM to analyze and securely rewrite code
user_prompt = (
    "Please review the following script and do all of the following in order:\n"
    "1) Identify the primary vulnerability and why it’s dangerous.\n"
    "2) Explain realistic impact and when it can be exploited.\n"
    "3) Rewrite the program securely while keeping the original functionality.\n"
    "4) Briefly list safer serialization options and when to use them.\n"
    f"Here is the code to analyze and refactor:\n\n```python\n{code_snippet}\n```"
)

# Structure messages for chat-style model input
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt},
]

# Start Llama with basic settings
llm = Llama(
    model_path=model_path,
    n_ctx=4096,  # Max text length it can handle
    n_threads=os.cpu_count(),  # CPU cores to use
    n_batch=1024,  # Tokens handled per step
    n_gpu_layers=-1,  # Run all layers on GPU
    chat_format="llama-2",  # Use chat-style replies
    use_mmap=True,  # Load model efficiently
    use_mlock=False,  # Don’t lock model in RAM
    verbose=False,  # Keep output clean
)

# Ask model to create a reply
resp = llm.create_chat_completion(
    messages=messages,  # Chat history so far
    max_tokens=1200,  # Max words in answer
    temperature=0.2,  # Lower = more focused
    top_p=0.9,  # Controls response variety
    top_k=40,  # Chooses from top words
    repeat_penalty=1.05,  # Avoids repeated phrases
    stop=["</s>", "[/INST]"],  # End reply markers
)

# Output the model's concise secure review
print(resp["choices"][0]["message"]["content"].strip())


# In[76]:
