# 🚀 Production Deployment Manifest & Clean Architecture Guide

This document outlines the **exact essential files** required for deploying the **AI-Powered Predictive Maintenance & Vehicle Health Monitoring System** to **Render** (Backend API & ML Engine) and **Vercel** (Next.js Frontend PWA), along with explicit instructions on which leftover files to safely exclude.

---

## 📋 Table of Contents
1. [Vercel Deployment Files (Frontend Next.js PWA)](#1-vercel-deployment-files-frontend-nextjs-pwa)
2. [Render Deployment Files (Backend FastAPI & ML Engine)](#2-render-deployment-files-backend-fastapi--ml-engine)
3. [Root Configuration & Documentation](#3-root-configuration--documentation)
4. [Files & Folders to EXCLUDE (Useless / Leftover)](#4-files--folders-to-exclude-useless--leftover)
5. [Automated Clean Migration Commands](#5-automated-clean-migration-commands)

---

## 1. Vercel Deployment Files (Frontend Next.js PWA)

These files power your modern Next.js 14 Web Dashboard, PWA Service Worker, and Real-time Telemetry Visualizations on **Vercel**.

```
frontend/
├── package.json               # Node.js dependencies & scripts
├── package-lock.json          # Locked dependency tree
├── next.config.mjs            # Next.js configuration & PWA headers
├── tsconfig.json              # TypeScript compiler configuration
├── tailwind.config.ts         # Tailwind CSS design system tokens
├── postcss.config.mjs         # PostCSS plugin rules
├── public/
│   ├── manifest.json          # PWA web manifest
│   ├── sw.js                  # PWA service worker
│   └── icons/                 # PWA application icons (192x192, 512x512)
└── src/
    ├── app/                   # Next.js App Router pages
    │   ├── layout.tsx         # Global app root layout & font loaders
    │   ├── page.tsx           # Main homepage / feature landing
    │   ├── globals.css        # Core design system CSS tokens
    │   ├── dashboard/page.tsx # Live vehicle telemetry dashboard
    │   ├── fleet/page.tsx     # Fleet management view
    │   ├── predict/page.tsx   # ML predictive health analysis
    │   ├── alerts/page.tsx    # DTC fault code & risk alert center
    │   ├── history/page.tsx   # Telemetry log history viewer
    │   ├── reports/page.tsx   # PDF health report generator view
    │   ├── analytics/page.tsx # Fleet-wide trend analytics
    │   ├── login/page.tsx     # Auth login view
    │   └── register/page.tsx  # User registration view
    ├── components/            # Reusable UI Components
    │   ├── Header.tsx         # Navigation header
    │   └── Sidebar.tsx        # Navigation sidebar
    ├── context/               # Global React Contexts
    │   ├── AuthContext.tsx    # Auth & token state manager
    │   └── ThemeContext.tsx   # Dark/Light theme manager
    ├── hooks/                 # Custom React Hooks
    │   └── useDashboard.ts    # Dashboard data fetching hook
    ├── lib/                   # Utility Libraries
    │   └── api.ts             # Axios/Fetch API client for Render backend
    └── types/                 # TypeScript Interfaces
        └── index.ts           # Vehicle, Telemetry, and Alert type definitions
```

---

## 2. Render Deployment Files (Backend FastAPI & ML Engine)

These files power your production REST API, ML Prediction Engine, Telemetry Ingestion, and Supabase PostgreSQL Database models on **Render**.

```
api/                           # Modular FastAPI Router Architecture
├── main.py                    # Main FastAPI application entry point
├── middleware.py              # Dynamic CORS & Security Headers
├── database.py                # Supabase PostgreSQL engine & session pool
├── db_proxy.py                # Database connection proxy
├── dependencies.py            # FastAPI dependency injection
├── health.py                  # Healthcheck endpoints (/health, /ping)
├── openapi.py                 # Customized OpenAPI schema generator
├── telemetry.py               # Telemetry logging & OpenTelemetry setup
├── websocket.py               # Real-time WebSocket telemetry stream server
└── routers/                   # Microservice Endpoint Routers
    ├── alerts.py              # Vehicle fault code alert management
    ├── auth.py                # Authentication (OAuth2, Keycloak, JWT)
    ├── dashboard.py           # Real-time fleet metrics & health scores
    ├── fleet.py               # Multi-vehicle fleet management
    ├── history.py             # Historical sensor readings
    ├── ml.py                  # ML predictions & model inference
    ├── predictions.py         # Failure risk forecasting & SHAP values
    ├── recommendations.py     # AI predictive maintenance actions
    ├── reports.py             # PDF vehicle health report export
    ├── simulator.py           # Live CAN-bus OBD telemetry generator
    ├── uploads.py             # Multi-part CSV telemetry batch ingestion
    └── vehicles.py            # Vehicle registration & spec lookup

core/                          # Core Domain Logic & Business Engines
├── config.py                  # Pydantic environment configuration settings
├── db.py                      # Database models & CRUD queries
├── health_score.py            # Dynamic vehicle health score calculation engine
├── explainability.py          # SHAP feature importance & failure risk engine
├── preprocessing.py           # Raw OBD sensor data normalizer & cleaner
├── recommendations.py         # Maintenance action recommendation rules
├── reports.py                 # ReportLab PDF generation engine
└── utils.py                   # Shared helper utilities

ml/                            # Machine Learning Engine & Pipeline
├── pipeline.py                # Complete end-to-end ML training pipeline
├── train.py                   # Model training & hyperparameter optimization
├── predict.py                 # Real-time failure risk inference engine
├── feature_engineering.py     # Time-series rolling sensor features
├── ml_models.py               # XGBoost, Random Forest & Anomaly detection
└── ml_registry.py             # Model versioning & metadata registry

auth/                          # Authentication & Security Layer
├── jwt.py                     # JWT token generation & verification
├── rbac.py                    # Role-Based Access Control (Admin/Fleet/Driver)
└── keycloak.py                # Enterprise Keycloak SSO integration

simulator/                     # OBD-II & CAN-Bus Telemetry Simulator
├── obd_simulator.py          # Real-time OBD PID stream simulator
├── sensor_generator.py       # Engine temp, oil pressure & RPM generator
└── vehicle_models.py          # Vehicle profile definitions (Sedan, Truck, EV)

ingest/                        # Streaming Telemetry Ingestion Layer
├── can_bus.py                 # Raw CAN-bus frame parser
├── mqtt_subscriber.py         # IoT MQTT telemetry listener
└── stream_processor.py        # Real-time windowed aggregation stream

monitoring/                    # System Health & Model Drift
├── drift_detector.py          # Evidently AI model drift detector
├── metrics_collector.py       # Sensor telemetry metrics collector
└── prometheus_exporter.py     # Prometheus metrics exporter (/metrics)

notifications/                 # Alerting & Messaging System
├── email_service.py           # SMTP alert email sender
├── push_service.py            # Web Push notification dispatcher
├── sms_service.py             # Twilio SMS dispatcher
└── webhook_service.py         # Outbound webhook alert integration

tasks/                         # Asynchronous Background Tasks
├── celery_app.py              # Celery worker & Redis queue setup
└── scheduled_jobs.py          # Periodic maintenance & drift check jobs

Dockerfile                     # Production Docker container image for Render
docker-compose.yml             # Local docker multi-container stack definition
requirements.txt               # Locked Python dependencies for Render
pyproject.toml                 # Project metadata & Python build configuration
alembic.ini                    # Database migration configuration
migrations/                    # Alembic SQL schema migration scripts
```

---

## 3. Root Configuration & Documentation

```
.gitignore                     # Strict Git exclusion rules (Blocks secrets & caches)
.dockerignore                  # Docker build exclusion rules
.env.example                   # Template environment variable file
README.md                      # Comprehensive project documentation
SETUP.md                       # Local & Cloud setup guide
```

---

## 4. Files & Folders to EXCLUDE (Useless / Leftover)

These directories and files are **development leftovers, old backups, or local caches** and **MUST NOT** be pushed to GitHub or cloud environments:

| Excluded Item | Why it should be excluded |
| :--- | :--- |
| **`_archive/`** | Old monolithic backend code from early development iterations. Fully superseded by `api/`. |
| **`tests/` & `test/`** | Unit test suites. Not required for cloud runtime execution on Vercel or Render. |
| **`testenv/` & `.venv/`** | Heavy local Python virtual environments containing thousands of local packages. |
| **`models/` & `ml/models/*.pkl`** | Heavy 100MB+ binary model pickles. ML models are dynamically trained and stored reproducibly in Supabase / ML registry. |
| **`vehicle_health.db` & `*.db`** | Local development SQLite database files. Production uses Supabase PostgreSQL. |
| **`frontend/node_modules/`** | Local Node packages (over 14,000 files). Automatically installed clean on Vercel during build. |
| **`frontend/.next/`** | Local Next.js build cache. Automatically compiled fresh on Vercel. |
| **`logs/` & `*.log`** | Temporary local application log files. |
| **`.pre-commit-config.yaml` & `.releaserc.json`** | Local developer tooling configs. |

---

## 5. Automated Clean Migration Commands

If you ever want to push **ONLY the clean production code** to your repository without any leftover files, run this single clean command sequence in your terminal:

```bash
# Step 1: Remove lock & reset index to clean state
rm -f .git/index .git/index.lock

# Step 2: Stage only essential production files
git add .gitignore .dockerignore .env.example README.md SETUP.md Dockerfile docker-compose.yml requirements.txt pyproject.toml alembic.ini api/ core/ ml/ auth/ simulator/ ingest/ monitoring/ notifications/ tasks/ migrations/ frontend/

# Step 3: Check that your staged status is 100% GREEN 🟢
git status

# Step 4: Commit and Push cleanly to GitHub
git commit -m "feat: complete production codebase for Vercel and Render deployment"
git push origin main --force
```

---

### 🎉 Summary
By following this manifest, your GitHub repository will contain **100% production-ready code**, enabling **Vercel** to build your Next.js dashboard seamlessly and **Render** to deploy your FastAPI backend with maximum speed and zero bloat!
