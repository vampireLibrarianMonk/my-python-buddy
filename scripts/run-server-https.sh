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
ENV_PATH="$PROJECT_DIR/.env"

# Basic logger
log() { echo "[$(date +%H:%M:%S)] $*"; }

# Collect Subject Alternative Name (SAN) entries
PUB_IP="${PUB_IP_OVERRIDE:-}"
PUB_DNS="${PUB_DNS_OVERRIDE:-}"

if [[ "${NO_METADATA:-0}" -eq 0 ]]; then
  TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || true)
  [[ -n "$TOKEN" ]] && PUB_IP="${PUB_IP:-$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/public-ipv4 || true)}"
  [[ -n "$TOKEN" ]] && PUB_DNS="${PUB_DNS:-$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/public-hostname || true)}"
fi

SAN=()
[[ -n "$PUB_DNS" ]] && SAN+=("$PUB_DNS")
[[ -n "$PUB_IP" ]] && SAN+=("$PUB_IP")
[[ "${INCLUDE_LOCALHOST:-1}" -eq 1 ]] && SAN+=(localhost 127.0.0.1 ::1)
SAN+=("$@")

if [[ ${#SAN[@]} -eq 0 || ( ${#SAN[@]} -eq 1 && -z "${SAN[0]}" ) ]]; then
  echo "[ERROR] No SANs provided"
  exit 1
fi

# Conda
conda_cmd="/home/my-python-buddy/miniconda3/etc/profile.d/conda.sh"
env_name="my-python-buddy"

cd "$PROJECT_DIR"

# Helper to read a key from .env without evaluating it
get_env_val() {
  local key="$1"
  [[ -f "$ENV_PATH" ]] || { echo ""; return 0; }
  # grab first match, strip leading/trailing spaces and CR
  local line
  line="$(grep -m1 -E "^${key}=" "$ENV_PATH" || true)"
  [[ -z "$line" ]] && { echo ""; return 0; }
  # keep everything after first "=", allow "=" in the value
  local val="${line#*=}"
  # trim carriage return and trailing spaces
  val="${val%%$'\r'}"
  # shellcheck disable=SC2001
  val="$(echo -n "$val" | sed 's/[[:space:]]*$//')"
  echo -n "$val"
}

# Helper to upsert KEY=VALUE into .env (creates file if missing)
upsert_env_kv() {
  local key="$1" val="$2"
  if [[ -f "$ENV_PATH" ]] && grep -q -E "^${key}=" "$ENV_PATH"; then
    # replace line in-place
    # shellcheck disable=SC2016
    sed -i "s#^${key}=.*#${key}=${val}#g" "$ENV_PATH"
  else
    echo "${key}=${val}" >> "$ENV_PATH"
  fi
}

# Gather existing values (if any)
EXISTING_USER="$(get_env_val DJANGO_SUPERUSER_USERNAME)"
EXISTING_EMAIL="$(get_env_val DJANGO_SUPERUSER_EMAIL)"
EXISTING_PASS="$(get_env_val DJANGO_SUPERUSER_PASSWORD)"

NEED_USER="${EXISTING_USER:-}"
NEED_EMAIL="${EXISTING_EMAIL:-}"
NEED_PASS="${EXISTING_PASS:-}"

ALL_PRESENT=1
[[ -z "$NEED_USER" ]] && ALL_PRESENT=0
[[ -z "$NEED_EMAIL" ]] && ALL_PRESENT=0
[[ -z "$NEED_PASS" ]] && ALL_PRESENT=0

if [[ "$ALL_PRESENT" -eq 1 ]]; then
  log ".env already has superuser vars; not modifying it."
  export DJANGO_SUPERUSER_USERNAME="$EXISTING_USER"
  export DJANGO_SUPERUSER_EMAIL="$EXISTING_EMAIL"
  export DJANGO_SUPERUSER_PASSWORD="$EXISTING_PASS"
else
  log "One or more superuser vars missing; generating/updating only missing values."
  # Defaults for any missing values
  : "${DJANGO_SUPERUSER_USERNAME:=${EXISTING_USER:-SuperUser}}"
  : "${DJANGO_SUPERUSER_EMAIL:=${EXISTING_EMAIL:-superuser@anemail.com}}"

  # Generate password if missing
  if [[ -z "${EXISTING_PASS:-}" ]]; then
    RANDOM_PASS="$(tr -dc 'A-Za-z0-9!@#$%&*_' < /dev/urandom | head -c 20 || true)"
    [[ -n "$RANDOM_PASS" ]] || { echo "[ERROR] Failed to generate secure random password" >&2; exit 1; }
    DJANGO_SUPERUSER_PASSWORD="$RANDOM_PASS"
  else
    DJANGO_SUPERUSER_PASSWORD="$EXISTING_PASS"
  fi

  export DJANGO_SUPERUSER_USERNAME DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD

  # Only upsert missing keys; do NOT rewrite existing non-empty values
  [[ -z "$EXISTING_USER"  ]] && upsert_env_kv "DJANGO_SUPERUSER_USERNAME" "$DJANGO_SUPERUSER_USERNAME"
  [[ -z "$EXISTING_EMAIL" ]] && upsert_env_kv "DJANGO_SUPERUSER_EMAIL"    "$DJANGO_SUPERUSER_EMAIL"
  [[ -z "$EXISTING_PASS"  ]] && upsert_env_kv "DJANGO_SUPERUSER_PASSWORD" "$DJANGO_SUPERUSER_PASSWORD"
fi

# Django: migrations, collectstatic, idempotent superuser/profile creation
log "Activating Conda env and setting up Django..."
bash -c "source '$conda_cmd' && conda activate '$env_name' && \
  python manage.py makemigrations base_application && \
  python manage.py migrate && \
  python manage.py collectstatic --noinput && \
  python manage.py shell -c \"
from django.contrib.auth import get_user_model
from django.db import transaction
from base_application.models import AccountProfile
import os

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME','').strip()
email    = os.environ.get('DJANGO_SUPERUSER_EMAIL','').strip()
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD','').strip()

if not username or not password:
    raise SystemExit('Missing DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD')

with transaction.atomic():
    user, created = User.objects.get_or_create(
        username=username,
        defaults={'email': email or ''}
    )
    # Ensure superuser/staff flags and password are set
    changed = False
    if not user.is_superuser:
        user.is_superuser = True; changed = True
    if not user.is_staff:
        user.is_staff = True; changed = True
    if email and user.email != email:
        user.email = email; changed = True
    # Only reset password on first creation; avoid clobbering on repeats
    if created:
        user.set_password(password); changed = True
    if changed:
        user.save()

    # Ensure AccountProfile exists and set must_change_password on first creation
    profile, p_created = AccountProfile.objects.get_or_create(user=user)
    if created:
        profile.must_change_password = True
        profile.save()
print(f'User: {username} (created={created})')
\""

# Activate conda for running uvicorn
source "$conda_cmd"
conda activate "$env_name"

log "Starting Uvicorn: $APP on https://$HOST:$PORT"
exec uvicorn "$APP" \
  --host "$HOST" --port "$PORT" \
  --ssl-certfile "$CERT" \
  --ssl-keyfile  "$KEY"
