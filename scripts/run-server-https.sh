#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[ERROR] Line $LINENO: $BASH_COMMAND" >&2' ERR

APP="core.asgi:application"
HOST="0.0.0.0"
PORT="8443"
CERT_DIR=/etc/ssl/local
CERT="${CERT_DIR}/server.crt"
KEY="${CERT_DIR}/server.key"

# Set HOME and PROJECT_DIR for user context
USER_HOME="/home/my-python-buddy"
PROJECT_DIR="$USER_HOME/my-python-buddy"

# Basic logger
log() { echo "[$(date +%H:%M:%S)] $*"; }

# Conda
conda_cmd="/home/my-python-buddy/miniconda3/etc/profile.d/conda.sh"
env_name="my-python-buddy"

cd "$PROJECT_DIR"

# Activate conda for running uvicorn
source "$conda_cmd"
conda activate "$env_name"

log "Starting Uvicorn: $APP on https://$HOST:$PORT"
exec uvicorn "$APP" \
  --host "$HOST" --port "$PORT" \
  --ssl-certfile "$CERT" \
  --ssl-keyfile  "$KEY"
