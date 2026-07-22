# Vehicle Health Monitor — Local macOS Setup & Development Guide (No Docker)

This guide provides instructions for setting up, running, and developing the Vehicle Health Monitor system natively on macOS without using Docker.

---

## 🚀 Quick Start (Zero-Config SQLite — 5 minutes)

The fastest path to get the backend and frontend running using SQLite and local Redis:

### 1. Install Prerequisites
Make sure you have [Homebrew](https://brew.sh/) installed, then run:
```bash
brew install redis node
brew services start redis
```

### 2. Set Up Backend
```bash
# Clone/Enter directory
cd AI-Powered-Predictive-Maintenance-Vehicle-Health-Monitoring-System-main

# Create Python virtual environment and activate
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install ruff pytest pytest-asyncio pytest-cov httpx pre-commit

# Setup environment file
cp .env.example .env
```

Edit your `.env` file to use SQLite as the database:
```env
DATABASE_URL=sqlite:///vehicle_health.db
REDIS_URL=redis://localhost:6379/0
ENV=development
SECRET_KEY=change-me-to-a-random-64-char-string
OAUTH_ENABLED=false
```

Run database migrations:
```bash
alembic upgrade head
```

### 3. Run Everything (Open 3 Terminals)

* **Terminal 1 — Backend API:**
  ```bash
  source .venv/bin/activate
  make api
  # Or: uvicorn api.main:app --reload --port 8000 --reload-exclude "frontend/node_modules/*"
  ```
  Visit: http://localhost:8000/api/docs (Swagger API Docs)

* **Terminal 2 — Frontend (Next.js):**
  ```bash
  cd frontend
  npm install
  npm run dev
  ```
  Visit: http://localhost:3000 (Next.js Web App)

* **Terminal 3 — Celery Worker (Task Queue):**
  ```bash
  source .venv/bin/activate
  celery -A tasks.retrain_task worker -l info
  ```

---

## 🛠️ Full Setup (Homebrew PostgreSQL & Redis)

For a production-like local setup, use PostgreSQL 16 instead of SQLite.

### 1. Install PostgreSQL & Redis via Homebrew
```bash
brew install postgresql@16 redis
```

### 2. Start Services
Configure macOS to launch PostgreSQL and Redis automatically on startup or manually as background services:
```bash
brew services start postgresql@16
brew services start redis
```

### 3. Create the Database & User
Run the following commands to create a user and a database for the application:
```bash
# Create a superuser named 'vhm'
createuser -s vhm

# Create the database owned by 'vhm'
createdb -O vhm vehicle_health
```

### 4. Configure Backend Environment
Update your `.env` file with the PostgreSQL connection string:
```env
DATABASE_URL=postgresql+asyncpg://vhm@localhost:5432/vehicle_health
REDIS_URL=redis://localhost:6379/0
ENV=development
SECRET_KEY=change-me-to-a-random-64-char-string
OAUTH_ENABLED=false
```

Apply database migrations:
```bash
alembic upgrade head
```

---

## 🖥️ Everyday Development Routine

When starting a development session, ensure the background services are active:
```bash
brew services start postgresql@16
brew services start redis
```

Then run the application processes in separate terminal sessions or tabs:
1. **Backend:** `source .venv/bin/activate && make api`
2. **Frontend:** `cd frontend && npm run dev`
3. **Celery Worker:** `source .venv/bin/activate && celery -A tasks.retrain_task worker -l info`

---

## 🧪 Running Tests & Simulators

### Running Tests
Make sure your virtual environment is active.

* **Backend Tests:**
  ```bash
  make test
  # Or: pytest tests/ -v --cov=. --cov-report=term
  ```
* **Frontend Tests:**
  ```bash
  cd frontend
  npx vitest run
  ```

### Running Simulators
The project includes OBD-II simulators to feed data to the API.

* **Single Vehicle Simulator (Healthy Profile):**
  ```bash
  source .venv/bin/activate
  make simulate
  # Or: python simulator/obd_simulator.py --interval 5 --profile healthy
  ```
* **Fleet Simulator (5 Vehicles, Mixed Profiles):**
  ```bash
  source .venv/bin/activate
  make fleet
  # Or: python simulator/fleet_simulator.py --vehicles 5 --interval 10
  ```
* **Generate Static Sample Data:**
  ```bash
  make generate-data
  # Or: python generate_data.py
  ```

---

## 📋 Environment Configuration Reference

The `.env` file controls all local service behavior.

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENV` | `development` | Environment mode (`development` or `production`) |
| `SECRET_KEY` | `change-me-...` | Cryptographic secret for signing sessions |
| `DATABASE_URL` | `sqlite:///vehicle_health.db` | Main database URL (use `postgresql+asyncpg://...` for PostgreSQL) |
| `REDIS_URL` | `redis://localhost:6379/0` | URL for the Redis cache & Celery task broker |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MAX_UPLOAD_SIZE_MB` | `200` | Maximum file size in MB for CSV uploads |
| `OAUTH_ENABLED` | `false` | Enable/disable Keycloak OAuth2 auth (keep `false` locally) |
| `ALLOWED_ORIGINS` | (local origins) | Comma-separated CORS allowed origins |

---

## 🔍 Local Troubleshooting

> [!IMPORTANT]
> Since Docker is not used, you are running processes directly on your host machine. Check standard macOS system logs and ports if you run into conflicts.

### PostgreSQL Connection Failures
* **Error:** `Connection refused` or `role "vhm" does not exist`
* **Fixes:**
  1. Check if Postgres is running: `brew services list`
  2. Start Postgres: `brew services start postgresql@16`
  3. Ensure the database user is created: `createuser -s vhm`
  4. Ensure the database is created: `createdb -O vhm vehicle_health`

### Redis Connection Failures
* **Error:** Celery or FastAPI logs show Redis connection errors.
* **Fixes:**
  1. Check if Redis is running: `brew services list`
  2. Start Redis: `brew services start redis`
  3. Verify ping: `redis-cli ping` (should respond with `PONG`)

### Port 8000 (Backend) or Port 3000 (Frontend) Already In Use
* **Error:** `[Errno 48] Address already in use`
* **Fixes:**
  Identify and terminate the process holding the port:
  ```bash
  lsof -i :8000
  kill -9 <PID>
  ```

### Python Version Mismatches
* **Error:** Packages fail to build or compile.
* **Fixes:**
  The project is built and verified with Python 3.11+. Make sure your virtual environment is using a compatible version:
  ```bash
  python3 --version
  ```

---

## ⌨️ Command Reference (Makefile)

The local `Makefile` contains useful shortcuts for local development without containerization:

```bash
make install          # Install Python dependencies from requirements.txt
make test             # Run backend test suite with coverage
make lint             # Check backend code style using Ruff
make api              # Start FastAPI locally on port 8000
make run              # Start the Next.js frontend locally
make migrate          # Upgrade database schemas to latest version
make migrate-fresh    # Re-create database schemas from scratch
make simulate         # Start a single OBD-II vehicle simulator
make fleet            # Start a fleet simulator (5 vehicles)
make generate-data    # Generate sample sensor readings CSV file
make clean            # Remove caches, log files, and test databases
```
./.venv/bin/python -m simulator.obd_simulator --vehicle-id HR-1234 --profile dynamic --interval 1 --username Naman0313 --password admin123 --api-url https://vehicle-health-api-ypj8.onrender.com/api/v1


git remote set-url origin https://github.com/Naman09746/AI-powered-vehicle-health-monitoring.git

git add -A

git commit -m "fix: CORS config, service worker clone bug, PWA icon, and initial project setup"

git push -u origin main --force
