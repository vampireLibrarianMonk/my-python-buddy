#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <timestamp>"
    echo "Example: $0 2025-10-30_1326"
    exit 1
fi

TS="$1"
MODEL_DIR="../models"
REGION=$(aws configure get region)

# Hard-coded expected filenames (with timestamp inserted dynamically)
EXPECTED_FILES=(
    "llama-2-7b-143k-codeAlpaca-${TS}.zip"
    "llama-2-7b-143k-codeAlpaca-q4_K_M-${TS}.gguf"
    "llama-2-gguf-7b-143k-codeAlpaca-${TS}-hash.txt"
    "llama-2-merged-7b-143k-codeAlpaca-${TS}-hash.txt"
)

echo "[*] Checking for required files in: $MODEL_DIR"
FOUND_FILES=()

# Verify each expected file exists
for fname in "${EXPECTED_FILES[@]}"; do
    FULL_PATH="${MODEL_DIR}/${fname}"
    if [[ -f "$FULL_PATH" ]]; then
        FOUND_FILES+=("$FULL_PATH")
    else
        echo "ERROR: Missing required file: $fullname"
        exit 1
    fi
done

#  Generate 16-character hash
RAND_HASH=$(openssl rand -hex 8)
BUCKET_NAME="model-artifacts-${RAND_HASH}"

echo "[*] Generated ID: $RAND_HASH"
echo "[*] S3 Bucket: $BUCKET_NAME"

# Display files and ask for confirmation
echo ""
echo "###############################################################"
echo "The following 4 files will be uploaded to $BUCKET_NAME"
printf ' - %s\n' "${FOUND_FILES[@]}"
echo "###############################################################"
echo ""

read -p "Proceed with upload? (y/N): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Cancelled."
    exit 0
fi

echo "Creating S3 bucket: $BUCKET_NAME in region: $REGION"

if [ "$REGION" = "us-east-1" ]; then
    # us-east-1 CANNOT have a LocationConstraint
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$REGION"
else
    # All other regions MUST have a LocationConstraint
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"
fi

echo "Waiting for bucket to exist..."
aws s3api wait bucket-exists --bucket "$BUCKET_NAME"

# Double-check existence using head-bucket
echo "Verifying bucket..."
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo "Bucket '$BUCKET_NAME' exists and is ready."
else
    echo "ERROR: Bucket '$BUCKET_NAME' does NOT exist."
    exit 1
fi

# Upload each file individually and generate 14-day presigned URL
echo "[*] Uploading files..."
for f in "${FOUND_FILES[@]}"; do
    BASENAME=$(basename "$f")

    echo "[*] Uploading: $BASENAME"
    aws s3 cp "$f" "s3://${BUCKET_NAME}/${BASENAME}"

    echo "[*] Creating presigned URL for: $BASENAME"
    PRESIGN_URL=$(aws s3 presign "s3://${BUCKET_NAME}/${BASENAME}" --expires-in 604800)

    echo "   Presigned URL:"
    echo "   curl -o /home/my-python-buddy/my-python-buddy/models/$BASENAME \"$PRESIGN_URL\""
    echo
done

echo ""
echo "###############################################################"
echo "UPLOAD COMPLETE"
echo "Bucket: s3://${BUCKET_NAME}/"
echo "Uploaded:"
printf ' - %s\n' "${FOUND_FILES[@]}"
echo "###############################################################"
