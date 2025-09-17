# my-python-buddy

## Project Definition
This project for the current branch `base-scaffolding` is a minimal example template that allows for the upload of a single `.py` file, persisted via SQLite and show a base output of templated analyzers and commenting that is the base for which actual security findings and LLM advice chain generation will occur. The end view that is currently functioning is a side-by-side view of the code (with line numbers) against the base template of security findings / advice chain statement template. Finally the project includes a healthcheck application programming interface (API) endpoint and basic file upload checking and file management implementation (e.g. list, download/view and delete).

## Intended Audience
Primary project developer who has put together a base template serving as a starter for code upload and analysis workflows in Django.

## User Guide
1. Start the development server.
```bash
python manage.py runserver
```
2. Go to the following page on the browser http://127.0.0.1:8000
3. Upload a `.py` file on the **Upload** page.
4. The file appears in **Previous uploads** with a **View/Download** link and an **Analysis** action.
5. Click **Analyze** to pick analyzers and view results (split view: source with line numbers + findings).
6. Use the trash icon to delete an entry. 
7. Visit the following page (http://127.0.0.1:8000/healthz/) what will become the primary interface API for checking the health of the server.
or
8. Use the following curl + jquery command for a "pretty" command line alternative to the browser:
```bash
curl -s http://127.0.0.1:8000/healthz/ | jq
```

# Developers Guide Notes
- Configure settings via an `.env` that the developer will derive from `.env.example`.
- DO NOT COMMIT the `.env` or fill out the `.env.example` with actual credentials. 
- Future work on a .pre-commit webhook will prevent unsafe practices in the future.
- File uploads are stored in `/media/uploads/`.
- Analysis status and metadata are persisted per file for table badges and re-runs.

## Conda

### Conda Environment Setup and Activation
```bash
conda create -n my-python-buddy -c conda-forge -y python=3.10 pip django=5
conda activate my-python-buddy
```

### Conda Environment File Export (ease of portability)
```bash
conda env export --no-builds | grep -v "^prefix: " > environment.yml
```

### Apply Database Migrations
```bash
python manage.py makemigrations base_application
python manage.py migrate
```

### Collect Static Assets 
```bash
python manage.py collectstatic --noinput
```

### Development Server Launch
```bash
python manage.py runserver
```

## User Setup

### Create an admin account for Django's built-in authentication, administration and login system.
```bash
python manage.py createsuperuser
````

### Choose a username for the superuser, default is your username.
```bash
Username (leave blank to use '$USER'): 
```

### Optional Email (only for when site has email server capability)
```bash
Email address: pmf141@psu.edu
```

### Set the superuser's password and then confirm it.
```bash
Password: 
Password (again): 
```

### Confirmation of successfully created account
```bash
Superuser created successfully.
```

### Regular User Creation (modify the three environment variables)
```bash
export DJANGO_SUPERUSER_USERNAME="regularUser"
export DJANGO_SUPERUSER_EMAIL="UserReg@anemail.com"
export DJANGO_SUPERUSER_PASSWORD="SuperSecureP@\$\$W0RD"

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

## Make Certificates to Enable HTTPS

### Install mkcert for Ubuntu
```bash
sudo apt install mkcert -y
```

### Trust mkcert’s local certificate authority:
```bash
mkcert -install
````

### Generate a cert for localhost:
```bash
mkcert localhost 127.0.0.1 ::1
```

### The following two files are created:
```bash
localhost+2.pem         # certificate
localhost+2-key.pem     # private key
```

### Use them with your HTTPS server (example with Uvicorn):
```bash
uvicorn core.asgi:application --host 127.0.0.1 --port 8443 \
  --ssl-certfile localhost+2.pem --ssl-keyfile localhost+2-key.pem
```

## Testing
This project will accumulate software tests in the form of acceptance, integration and unit tests as it progresses. Before using read teh command line usage below and the pydoc with each test file, class and method under the `base_application/tests` directory. 

### Command-line Usage

### Run all tests
```bash
python manage.py test
```

### Run only a single test `test_upload`
```bash
python manage.py test base_application.tests.test_upload -v 2
````

### Run a single test class 
```bash
python manage.py test base_application.tests.test_upload.UploadViewTests -v 2
```

### Run a single test
```bash
python manage.py test base_application.tests.test_upload.UploadViewTests.test_accepts_valid_py -v 2
```

### Useful flags for efficiency and speed of execution
```bash
python manage.py test --keepdb       # faster runs by re-using database
python manage.py test --parallel 4   # parallel execution
```