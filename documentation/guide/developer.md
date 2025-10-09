# Developer Guide: my-python-buddy

## Project Definition

This project for the current branch `base-scaffolding` is a minimal example template designed for file upload and analysis workflows in Django. It enables uploading a single `.py` file, persisting it via SQLite and displaying results using templated analyzers. These analyzers currently act as placeholders for future integration of actual security findings and LLM-driven advice chains. The code viewer displays uploaded code with line numbers alongside the template findings panel. The project also includes a healthcheck API endpoint (`healthz`) and a basic implementation for file management, such as listing, viewing/downloading and deleting uploaded files.

## Intended Audience

This guide is intended for developers who are configuring, extending, or maintaining the project. It provides implementation details, environment setup, configuration guidance and testing instructions.

---

## Developer Notes

- **Configuration Management:**
  All sensitive settings should be placed in an `.env` file derived from `.env.example`.
  Do **not** commit `.env` files to version control or populate `.env.example` with real credentials.

- **Secure Practices:**
  A `.pre-commit` webhook exists to enforce safe coding practices, formatting, linting and spell checking.

- **File Storage:**
  File uploads are stored in `/media/uploads/`. Developers should ensure that this directory is properly mounted and secured.

- **Metadata Persistence:**
  Analysis status and metadata are stored per file. This enables table badges, historical entries and re-runs of analyses.

---

## Local HTTPS Setup with mkcert

To simulate HTTPS locally for development and testing, `mkcert` can be used to generate self-signed certificates trusted by your machine.

### Install mkcert (Ubuntu)

```bash
sudo apt install mkcert -y
```

### Trust mkcert’s local certificate authority

```bash
mkcert -install
```

### Generate a certificate for localhost

```bash
mkcert localhost 127.0.0.1 ::1
```

This creates the following files:

```bash
localhost+2.pem         # certificate
localhost+2-key.pem     # private key
```

### Use with uvicorn

```bash
uvicorn core.asgi:application --host 127.0.0.1 --port 8443   --ssl-certfile localhost+2.pem --ssl-keyfile localhost+2-key.pem
```

---

## User Setup

### Create an admin account for Django's built-in authentication, administration and login system.

```bash
python manage.py createsuperuser
```

### Choose a username for the superuser, default is your username.

```bash
Username (leave blank to use '$USER'):
Optional Email (only for when site has email server capability)
Email address: pmf141@psu.edu
Set the superuser's password and then confirm it.
Password:
Password (again):
Confirmation of successfully created account
Superuser created successfully.
```

### Regular User Creation (modify the three environment variables)

```bash
export DJANGO_SUPERUSER_USERNAME="regularUser"
export DJANGO_SUPERUSER_EMAIL="UserReg@anemail.com"
export DJANGO_SUPERUSER_PASSWORD=# Fill in password

python manage.py shell -c "
from django.contrib.auth import get_user_model;
from base_application.models import AccountProfile;
import os;
U = get_user_model();
u = U.objects.create_user(
    os.environ['DJANGO_SUPERUSER_USERNAME'],
    os.environ['DJANGO_SUPERUSER_EMAIL'],
    os.environ['DJANGO_SUPERUSER_PASSWORD']
);
p = AccountProfile.objects.get(user=u);
p.must_change_password = True;
p.save()
"
```

---

# Amazon EC2 Support Scripts.

For brevity there exists two support scripts once your EC2 Instance is running in AWS. This project does not currently cover the setup of cloud infrastructure to support deployment. The scripts are meant to be run in `sudo`.

---

## Setup on Ubuntu 22.04

This script prepares an Ubuntu environment with the necessary dependencies for the project.

```bash
bash ubuntu-setup.sh
```

---

## Run the HTTPS Server

This script launches the Django application using `uvicorn` with HTTPS enabled. It ensures the server uses the generated mkcert SSL certificate and key, allowing developers to test the application securely over HTTPS on localhost. The script is written have re-run capability if for any reason you have to stop the service.

```bash
bash run-server-https.sh
```

---

## Conda Environment Setup

Conda provides a way for the developer to reproduce, reliably, their environment with specific versions down to the hash of the package. This ensures consistent experience from developer to developer and from developer to user across machines.

### Install miniconda

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash ~/Miniconda3-latest-Linux-x86_64.sh -b -p "$HOME/miniconda3" && \
  eval "$("$HOME/miniconda3/bin/conda" shell.bash hook)" && \
  "$HOME/miniconda3/bin/conda" init bash && \
  conda --version
```

### Accept Terms of Service

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

### Create and activate environment

```bash
conda create -f environment.yml
conda activate my-python-buddy
```

### Export environment file (for portability)

```bash
conda env export --no-builds | grep -v "^prefix: " > environment.yml
```

---

## Database and Static Files

### Apply database migrations

```bash
python manage.py makemigrations base_application
python manage.py migrate
```

### Collect static assets

```bash
python manage.py collectstatic --noinput
```

---

## Healthcheck API Endpoint

The application includes a `/healthz/` endpoint for monitoring purposes.

- **URL:** `https://127.0.0.1:8443/healthz/`
- **Method:** `GET`
- **Response:** JSON object containing a status indicator (e.g., `{"status": "ok", "app": "my-python-buddy", "env": "dev", "version": "0.0.1", "build": "local", "debug": true, "time": 1758418830.0463486}`).
- **Purpose:** Allows developers and deployment systems to verify that the server is running and responsive.
- **Usage:** This endpoint should be integrated into monitoring pipelines or container orchestration liveness checks.

---

## Testing

The project will accumulate a suite of **unit**, **integration** and **acceptance** tests as development progresses.

- **Test Files Location:** `base_application/tests`
- **Test Documentation:** `documentation/test`

### Run all tests

```bash
python manage.py test
```

### Run a specific test file

```bash
python manage.py test base_application.tests.test_upload -v 2
```

### Run a single test class

```bash
python manage.py test base_application.tests.test_upload.UploadViewTests -v 2
```

### Run a single test method

```bash
python manage.py test base_application.tests.test_upload.UploadViewTests.test_accepts_valid_py -v 2
```

### Useful flags

```bash
python manage.py test --keepdb       # reuse database for faster test cycles
python manage.py test --parallel 4   # run tests in parallel
```
