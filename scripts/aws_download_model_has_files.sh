#!/usr/bin/env bash
set -euo pipefail


#  Validate Arguments
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <timestamp> <s3-bucket>"
    echo "Example: $0 2025-10-30_1326 model-artifacts-d6sj2ksal0cv91b45"
    exit 1
fi

TIME_STAMP="$1"
S3_BUCKET="$2"


#  Validate Working Directory
REQ_DIR="my-python-buddy/scripts"
CUR_DIR=$(basename "$PWD")
PARENT_DIR=$(basename "$(dirname "$PWD")")

if [[ "$PARENT_DIR/$CUR_DIR" != "$REQ_DIR" ]]; then
    echo "ERROR: This script must be run from: $REQ_DIR"
    echo "Current location: $PARENT_DIR/$CUR_DIR"
    exit 1
fi

echo "Working directory validated: $REQ_DIR"


#  Prepare Model Directory
MODEL_DIR="../models"

if [[ ! -d "$MODEL_DIR" ]]; then
    echo "Creating model directory: $MODEL_DIR"
    mkdir -p "$MODEL_DIR"
else
    echo "Model directory exists."
fi


#  Hard-coded file definitions
FILES=(
    "llama-2-7b-143k-codeAlpaca-${TIME_STAMP}.zip"
    "llama-2-7b-143k-codeAlpaca-q4_K_M-${TIME_STAMP}.gguf"
    "llama-2-gguf-7b-143k-codeAlpaca-${TIME_STAMP}-hash.txt"
    "llama-2-merged-7b-143k-codeAlpaca-${TIME_STAMP}-hash.txt"
)

echo "Expecting the following model files:"
printf ' - %s\n' "${FILES[@]}"


#  Check each file exists and download
echo ""
echo "Starting download from bucket: $S3_BUCKET"
echo ""

for f in "${FILES[@]}"; do
    S3_PATH="s3://${S3_BUCKET}/${f}"

    echo "Downloading: $f"
    aws s3 cp "$S3_PATH" "$MODEL_DIR/$f"
done

echo ""
echo "##############################################"
echo "DOWNLOAD COMPLETE"
echo "Bucket: $S3_BUCKET"
echo "Saved to: $MODEL_DIR/"
printf ' - %s\n' "${FILES[@]}"
echo "##############################################"
