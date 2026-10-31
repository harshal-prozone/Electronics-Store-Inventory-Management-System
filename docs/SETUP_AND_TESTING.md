# Setup and Testing Guide

This guide covers a fresh local setup of the Electronics Store Inventory Management System (ESIMS), database initialization, administrator creation, application startup, automated tests, and troubleshooting.

Run commands from the repository root (the directory containing `app.py` and `requirements.txt`).

## 1. Prerequisites

- Git.
- Python 3.12 recommended: the GitHub Actions workflow uses Python 3.12. The project README specifies Python 3.10+; the maintainer has also run the project with Python 3.14.7.
- `pip`, included with Python.
- macOS, Linux, or Windows with a terminal.

SQLite is included with Python. You do not need to install or run a separate database server.

Check your tools:

```bash
git --version
python3 --version
python3 -m pip --version
```

On Windows, use `py --version` and `py -m pip --version` if needed.

## 2. Clone and install

```bash
git clone https://github.com/harshal-prozone/Electronics-Store-Inventory-Management-System.git
cd Electronics-Store-Inventory-Management-System
python3 -m venv .venv
```

Activate the environment.

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The requirements file installs Flask, Flask-WTF, pytest, and ReportLab. Playwright is optional and is only needed for the browser acceptance script.

## 3. Configure environment variables

The application reads these variables:

| Variable | Purpose |
|---|---|
| `APP_ENV` | Use `development` for local work. |
| `SECRET_KEY` | Signs Flask sessions. Set a private, persistent random value. If omitted in development, the app generates a temporary key; sessions will not survive a restart. Production requires an explicit value. |
| `DATABASE_PATH` | SQLite file path. Defaults to `instance/inventory.db`, relative to the repository root. |
| `ADMIN_USERNAME` | Optional username used for first-run administrator seeding when `ADMIN_PASSWORD` is also set. |
| `ADMIN_EMAIL` | Optional email used for first-run administrator seeding when `ADMIN_PASSWORD` is also set. |
| `ADMIN_PASSWORD` | Optional first-run administrator password. Must be at least 10 characters. Prefer the interactive `create-admin` command. |
| `COOKIE_SECURE` | Use `0` for local HTTP and `1` when deployed over HTTPS. |

Recommended macOS/Linux development configuration:

```bash
export APP_ENV=development
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_PATH="instance/inventory.db"
export COOKIE_SECURE=0
```

Keep the same secret in the terminal session. For a persistent local setup, the repository provides `.env.example`. Copy it to `.env`, generate a secret with the Python command above, and put that value in `.env`:

```bash
cp .env.example .env
python -c 'import secrets; print(secrets.token_hex(32))'
```

**Important:** this project does not automatically load `.env`; `python-dotenv` is not in `requirements.txt`. Load it explicitly in macOS/Linux bash or zsh:

```bash
set -a
source .env
set +a
```

Never commit `.env`, passwords, or real secrets. `.env` and `instance/` are ignored by Git.

## 4. Initialize SQLite and create an administrator

Initialize the database:

```bash
flask --app app init-db
```

This creates the schema, applies supported schema migrations, and inserts sample inventory when the component table is empty. The default database is `instance/inventory.db`; its parent directory is created automatically. Set `DATABASE_PATH` before running the command to use another location.

A normal fresh installation does not receive a known default administrator password. Create an administrator interactively:

```bash
flask --app app create-admin
```

Enter a username, email, and password when prompted. The password must be at least 10 characters. The password prompt does not display typed characters. The command fails if the username or email already exists.

You can supply username and email as options; the password is still prompted:

```bash
flask --app app create-admin --username admin --email admin@example.local
```

Alternatively, the application can seed an administrator on first initialization if `ADMIN_PASSWORD`, `ADMIN_USERNAME`, and `ADMIN_EMAIL` are set before initialization. The interactive command is preferred. Changing these variables later does not reset an existing password.

Importing `app.py` creates the Flask application and initializes its configured database. The explicit `init-db` CLI command is also available. Initialization is not a command to erase user data.

## 5. Run the application

With the virtual environment active and configuration loaded:

```bash
flask --app app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and sign in with the administrator account you created. Stop the server with `Ctrl+C`.

Health check: [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health). A healthy response is HTTP 200 with JSON indicating `status: ok` and `database: ok`.

The Flask development server is for local development only. Production requires a production WSGI server, HTTPS, a persistent strong secret, secure cookie configuration, backups, and monitoring.

## 6. Run automated tests

Run the full suite from the repository root:

```bash
pytest -q
```

For verbose output:

```bash
pytest -v
```

Run individual test modules:

```bash
pytest -v tests/test_inventory_service.py
pytest -v tests/test_inventory_workflow_integration.py
pytest -v tests/test_csv_import.py
pytest -v tests/test_issue9_transactions.py
pytest -v tests/test_web_app.py
```

The integration workflow tests use an isolated temporary database and cover component persistence, stock-in/stock-out, transaction history, insufficient stock, missing components, and rollback behavior. Pytest configuration is in `pytest.ini`; tests are discovered under `tests/`.

Before committing, run:

```bash
git diff --check
```

This checks whitespace errors in the diff; it does not replace tests.

### Optional performance acceptance test

```bash
python scripts/performance_test.py
```

This script creates a temporary database with at least 5,000 components, starts a loopback threaded Flask server, and sends 100 listing/search/filter requests with 10 workers. It passes when all requests succeed and at least 95% finish within two seconds. This is a coursework acceptance check, not a production-network benchmark.

### Optional cross-browser acceptance test

The browser script requires Playwright and a matching installed browser. Playwright is not part of the runtime requirements:

```bash
python -m pip install playwright
python -m playwright install chromium
```

For an installed Google Chrome channel:

```bash
ESIMS_BROWSER=chrome python scripts/browser_acceptance.py
```

The script accepts `chrome`, `edge`, or `firefox`; install the corresponding browser and set `ESIMS_BROWSER` accordingly. It creates a temporary database and test accounts. GitHub Actions runs this matrix on Python 3.12.

## 7. Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| `ModuleNotFoundError` | Virtual environment is inactive or dependencies are missing | Activate `.venv`; run `python -m pip install -r requirements.txt`. |
| `flask: command not found` | Virtual environment is inactive | Activate `.venv`, or use `python -m flask --app app run --debug`. |
| Flask app cannot be located | Command run outside repository root or missing app target | `cd` to the directory containing `app.py`; include `--app app`. |
| No administrator can sign in | No admin exists in the selected database or credentials are incorrect | Run `flask --app app create-admin`. There is no default admin password. |
| Username/email already in use | That identity already exists | Use the existing account or choose another username/email. Do not delete a database without checking its contents. |
| `SECRET_KEY must be set when APP_ENV=production` | Production mode has no configured secret | Set a strong private `SECRET_KEY`. |
| `.env` changes have no effect | `.env` is not automatically loaded | Load it with `set -a; source .env; set +a`, or export variables directly. |
| Wrong or empty database appears | `DATABASE_PATH` differs between sessions or a relative path is resolved from another working directory | Run from repository root and set `DATABASE_PATH` consistently. |
| SQLite `database is locked` | Another process is writing to the database | Stop duplicate servers/scripts, wait for the active write to finish, and retry. The app sets a 10-second busy timeout. Do not delete needed data. |
| Port 5000 is already in use | Another process owns the port | Stop it or run `flask --app app run --debug --port 5001`, then open `http://127.0.0.1:5001`. |
| Playwright cannot find a browser | The selected browser is not installed or its channel is unavailable | Install the browser and set `ESIMS_BROWSER` to `chrome`, `edge`, or `firefox`. |

## 8. Database and secret safety

- Default database: `instance/inventory.db`.
- Set `DATABASE_PATH` to use a separate file for experiments.
- `instance/` and `.env` are ignored by Git; do not force-add them.
- Back up the database before manual or destructive operations.
- Do not share databases containing real user data.
- Never commit passwords, API keys, or production secrets.
- Unit/integration tests and the performance/browser scripts use isolated test or temporary databases.

## 9. Independent teammate verification

A second team member must follow this checklist on their own machine from a fresh clone, not from the maintainer's existing virtual environment or database.

- [ ] Clone the repository and record OS and Python version.
- [ ] Create and activate a fresh virtual environment.
- [ ] Install dependencies using only `requirements.txt`.
- [ ] Configure a private development `SECRET_KEY` and fresh `DATABASE_PATH`.
- [ ] Run `flask --app app init-db`.
- [ ] Create an administrator using `flask --app app create-admin`.
- [ ] Start the app using `flask --app app run --debug` and sign in.
- [ ] Confirm `/health` returns HTTP 200 and reports the database as healthy.
- [ ] Run `pytest -q` and record the exact test summary.
- [ ] Record any deviations, errors, and resolutions.

Record the verifier's GitHub handle, date, OS, Python version, test summary, and any issues in Issue #24 or its pull request. Do not record passwords or secret values. The CI smoke test is additional evidence; it does not replace this independent human verification.

## 10. Continuous integration

The workflow at `.github/workflows/tests.yml` uses Python 3.12. It installs `requirements.txt`, runs `pytest -q`, runs the performance acceptance script, initializes a clean database, creates an administrator, checks `/health`, and runs browser acceptance on Chrome, Edge, and Firefox.

Use the checks on the relevant pull request as current pass/fail evidence. Results can change between commits; an old passing run does not prove that a newer commit passed.
