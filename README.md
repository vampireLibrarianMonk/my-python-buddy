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

## Developers Guide
- Configure settings via an `.env` that the developer will derive from `.env.example`.
- DO NOT COMMIT the `.env` or fill out the `.env.example` with actual credentials. 
- Future work on a .pre-commit webhook will prevent unsafe practices in the future.
- File uploads are stored in `/media/uploads/`.
- Analysis status and metadata are persisted per file for table badges and re-runs.

### Conda Environment Setup and Activation
```bash
conda create -n my-python-buddy -c conda-forge -y python=3.10 pip django=5
conda activate my-python-buddy
```

### Conda Environment File Export (ease of portability)
```bash
conda env export --no-builds | grep -v "^prefix: " > environment.yml
```

## Apply Database Migrations
```bash
python manage.py makemigrations base_application
python manage.py migrate
```

## Collect Static Assets 
```bash
python manage.py collectstatic --noinput
```

## Development Server Launch
```bash
python manage.py runserver
```

# Testing
This project will accumulate software tests in the form of acceptance, integration and unit tests as it progresses. Before using read teh command line usage below and the pydoc with each test file, class and method under the `base_application/tests` directory. 

## Command-line Usage

### Run all tests
python manage.py test

### Run only a single test `test_upload`
python manage.py test base_application.tests.test_upload -v 2

### Run a single test class 
python manage.py test base_application.tests.test_upload.UploadViewTests -v 2

### Run a single test
python manage.py test base_application.tests.test_upload.UploadViewTests.test_accepts_valid_py -v 2

### Useful flags for efficiency and speed of execution
python manage.py test --keepdb       # faster runs by re-using database
python manage.py test --parallel 4   # parallel execution
```