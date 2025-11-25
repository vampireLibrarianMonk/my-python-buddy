#!/bin/bash
set -e

REPO="https://github.com/vampireLibrarianMonk/my-python-buddy.git"

BRANCH="$1"

# Error handling: missing branch argument
if [ -z "${BRANCH:-}" ]; then
  echo "Error: Missing required branch name."
  echo "Usage: $0 <branch>"
  echo "Example: $0 name-of-branch"
  exit 1
fi

# Validate branch name format (basic Git branch rules)
if ! [[ "$BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "Error: Invalid branch name: '$BRANCH'"
  echo "Allowed characters: letters, numbers, ., _, -, /"
  exit 1
fi

# Validate that a branch exists on the remote repository
if ! git ls-remote --heads "$REPO" "$BRANCH" >/dev/null 2>&1; then
  echo "Error: Branch '$BRANCH' does not exist in remote repository: $REPO"
  exit 1
fi

echo "Branch '$BRANCH' is valid and exists on remote."

# Create user 'my-python-buddy' if not exists
if ! id "my-python-buddy" &>/dev/null; then
  sudo adduser --disabled-password --gecos "" my-python-buddy
  sudo usermod -aG sudo my-python-buddy
fi

# Set HOME and PROJECT_DIR for user context
USER_HOME="/home/my-python-buddy"
PROJECT_DIR="$USER_HOME/my-python-buddy"

sudo mkdir -p /home/my-python-buddy
sudo chown my-python-buddy:my-python-buddy /home/my-python-buddy

# EC2 Ubuntu user-data: install dependencies, clone repo/branch and create .env with cloud-aware hosts/origins.
echo "[*] Updating packages and installing prerequisites..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y build-essential bzip2 cmake curl gcc-12 g++-12 git mkcert wget

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
  chown my-python-buddy:my-python-buddy "$KEY"
  chmod 444 "$CERT"
  chown my-python-buddy:my-python-buddy "$CERT"
else
  log "Using existing cert/key at $CERT_DIR"
fi

# Display SANs
log "Certificate SANs:"
openssl x509 -in "$CERT" -noout -text | grep -A2 "Subject Alternative Name" || true
[[ -f "$CERT" && -f "$KEY" ]] || { echo "[ERROR] TLS cert or key not found."; exit 1; }

# Everything below runs as 'my-python-buddy'
sudo -u my-python-buddy env PUB_IP="$PUB_IP" PUB_DNS="$PUB_DNS" USER_HOME="$USER_HOME" BRANCH="$BRANCH" REPO="$REPO" bash <<'EOF'
#!/bin/bash
set -euo pipefail

echo "[*] Preparing project directory..."
PROJECT_DIR="$USER_HOME/my-python-buddy"
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "    - Repo exists, pulling latest..."
  git -C "$PROJECT_DIR" fetch --all
else
  echo "    - Cloning fresh copy..."
  git clone $REPO "$PROJECT_DIR"
fi

echo "[*] Switching to branch: $BRANCH"
cd "$PROJECT_DIR"
git checkout $BRANCH || (git fetch origin $BRANCH && git checkout $BRANCH)

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

echo "Attempting to create Conda environment from environment.yml..."
MAX_RETRIES=5
RETRY_DELAY=10
ATTEMPT=1

while [ $ATTEMPT -le $MAX_RETRIES ]; do
  echo "  - Attempt $ATTEMPT of $MAX_RETRIES..."
  if "$USER_HOME/miniconda3/bin/conda" env create -f environment.yml; then
    echo "Conda environment created successfully."
    break
  else
    echo "Conda failed to create environment (likely network error)."
    if [ $ATTEMPT -eq $MAX_RETRIES ]; then
      echo "All attempts failed. Please check your network or proxy settings."
      exit 1
    fi
    echo "  - Retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
    ((ATTEMPT++))
  fi
done

log "Setup completed."
log "    Repository:        $PROJECT_DIR"
echo "    Branch:            $BRANCH"
echo "    Public IP:         ${PUB_IP:-<none>}"
echo "    Public DNS:        ${PUB_DNS:-<none>}"
echo "    .env created with cloud-aware ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS."
echo "    mkcert CA Root:    $(mkcert -CAROOT 2>/dev/null || echo '<not-found>')"

echo "Installing REDIS Server..."

sudo apt update && sudo apt install -y redis-server
echo "Redis installed."
echo "Enabling Redis on boot..."
sudo systemctl enable redis
sudo systemctl is-active --quiet redis && echo "Redis is running." || echo "Redis is NOT running."
redis-cli ping | grep -q PONG && echo "Redis is responding." || echo "Redis is NOT responding."

echo "Installing CUDA and NVIDIA Driver..."

# Download CUDA 12.4.1 installer
wget https://developer.download.nvidia.com/compute/cuda/12.4.1/local_installers/cuda_12.4.1_550.54.15_linux.run

# Run the installer silently (designated CC version, toolkit, driver, override warnings)
sudo CC=/usr/bin/gcc-12 CXX=/usr/bin/g++-12 sh cuda_12.4.1_550.54.15_linux.run --silent --toolkit --driver --override

# Load the NVIDIA kernel module
sudo modprobe nvidia

# Verify that the driver is active
nvidia-smi || echo "nvidia-smi failed: NVIDIA driver may not be loaded properly"

# Set up environment variables system-wide
sudo tee /etc/profile.d/cuda.sh > /dev/null << 'EOF'
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
EOF

# Apply environment changes for current session
source /etc/profile.d/cuda.sh

# Load Conda environment
eval "$($USER_HOME/miniconda3/bin/conda shell.bash hook)"
conda activate my-python-buddy

# Install llama-cpp-python with CUDA support using all available processors
CMAKE_ARGS="-DGGML_CUDA=on" PIP_BUILD_ARGS="--parallel $(nproc)" pip install llama-cpp-python

# Reboot for the required activation of the driver
echo "Rebooting to activate the NVIDIA driver..."
sudo reboot