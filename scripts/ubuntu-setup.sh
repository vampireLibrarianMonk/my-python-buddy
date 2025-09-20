#!/bin/bash
set -e

# Create user 'my-python-buddy' if not exists
if ! id "my-python-buddy" &>/dev/null; then
  sudo adduser --disabled-password --gecos "" my-python-buddy
  sudo usermod -aG sudo my-python-buddy
fi

# Set HOME and PROJECT_DIR for user context
USER_HOME="/home/my-python-buddy"
PROJECT_DIR="$USER_HOME/my-python-buddy"

# EC2 Ubuntu user-data: install dependencies, clone repo/branch and create .env with cloud-aware hosts/origins.
echo "[*] Updating packages and installing prerequisites..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git bzip2 curl mkcert wget

# Basic logger
log() { echo "[$(date +%H:%M:%S)] $*"; }

# Check dependencies
for bin in curl mkcert openssl; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing '$bin'"; exit 127; }
done

# Certificate and Key locations
CERT_DIR="/etc/ssl/local"
CERT="$CERT_DIR/server.crt"
KEY="$CERT_DIR/server.key"
INCLUDE_LOCALHOST=1
FORCE_REGEN=0
NO_METADATA=0

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

log "SANs: ${SAN[*]}"

# Generate or reuse cert
mkdir -p "$CERT_DIR"
if [[ "${FORCE_REGEN:-0}" -eq 1 || ! -f "$CERT" || ! -f "$KEY" ]]; then
  log "Generating cert/key with mkcert..."
  tmpdir=$(mktemp -d)
  trap 'rm -rf "$tmpdir"' EXIT
  mkcert -key-file "$tmpdir/server.key" -cert-file "$tmpdir/server.crt" "${SAN[@]}"
  mv "$tmpdir/server.key" "$KEY"
  mv "$tmpdir/server.crt" "$CERT"
  chmod 600 "$KEY"
  chmod 444 "$CERT"
else
  log "Using existing cert/key at $CERT_DIR"
fi

# Display SANs
log "Certificate SANs:"
openssl x509 -in "$CERT" -noout -text | grep -A2 "Subject Alternative Name" || true
[[ -f "$CERT" && -f "$KEY" ]] || { echo "[ERROR] TLS cert or key not found."; exit 1; }

# Everything below runs as 'my-python-buddy'
sudo -u my-python-buddy env PUB_IP="$PUB_IP" PUB_DNS="$PUB_DNS" USER_HOME="$USER_HOME" bash <<'EOF'
#!/bin/bash
set -euo pipefail

echo "[*] Preparing project directory..."
PROJECT_DIR="$USER_HOME/my-python-buddy"
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "    - Repo exists, pulling latest..."
  git -C "$PROJECT_DIR" fetch --all
else
  echo "    - Cloning fresh copy..."
  git clone https://github.com/vampireLibrarianMonk/my-python-buddy.git "$PROJECT_DIR"
fi

echo "[*] Switching to branch: base-scaffolding"
cd "$PROJECT_DIR"
git checkout base-scaffolding || (git fetch origin base-scaffolding && git checkout base-scaffolding)

echo "[*] Generating Django SECRET_KEY..."
DJANGO_SECRET_KEY="$(python3 - <<'PY'
from secrets import token_urlsafe
print("django-insecure-" + token_urlsafe(50))
PY
)"

echo "[*] Building ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS..."
ALLOWED="127.0.0.1,localhost"
[ -n "$PUB_IP" ] && ALLOWED="$ALLOWED,$PUB_IP"
[ -n "$PUB_DNS" ] && ALLOWED="$ALLOWED,$PUB_DNS"

CSRF="https://127.0.0.1:8443,https://localhost:8443"
[ -n "$PUB_IP" ] && CSRF="$CSRF,https://$PUB_IP:8443"
[ -n "$PUB_DNS" ] && CSRF="$CSRF,https://$PUB_DNS:8443"

echo "[*] Writing .env ..."

VERSION_FILE="$PROJECT_DIR/VERSION"
if [[ -f "$VERSION_FILE" ]]; then
  VERSION=$(head -n 1 "$VERSION_FILE" | tr -d '\r\n')
  [[ -z "$VERSION" ]] && VERSION="no-version-detected"
else
  VERSION="no-version-detected"
fi

cat > "$PROJECT_DIR/.env" <<EOF
APP_NAME=my-python-buddy
APP_ENV=dev
APP_VERSION=$VERSION
APP_BUILD=cloud
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$ALLOWED
DJANGO_CSRF_TRUSTED_ORIGINS=$CSRF
EOF

echo "[*] (Optional) Trust mkcert local certificate authority for this host"
sudo mkcert -install || true

# Install Miniconda
echo "[*] Installing Miniconda ..."
cd "$USER_HOME"
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p "$USER_HOME/miniconda3"
eval "$($USER_HOME/miniconda3/bin/conda shell.bash hook)"
$USER_HOME/miniconda3/bin/conda init bash
$USER_HOME/miniconda3/bin/conda --version

# Accept Terms of Service
$USER_HOME/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
$USER_HOME/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# Conda environment setup from yml and activate
cd "$PROJECT_DIR"
$USER_HOME/miniconda3/bin/conda env create -f environment.yml

log "[✓] Setup completed."
log "    Repository:        $PROJECT_DIR"
echo "    Branch:            base-scaffolding"
echo "    Public IP:         ${PUB_IP:-<none>}"
echo "    Public DNS:        ${PUB_DNS:-<none>}"
echo "    .env created with cloud-aware ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS."
echo "    mkcert CA Root:    $(mkcert -CAROOT 2>/dev/null || echo '<not-found>')"