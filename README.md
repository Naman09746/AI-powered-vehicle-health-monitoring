# 🚗 AI-Powered Predictive Maintenance & Vehicle Health Monitoring System

> **Version 2.0.0** — A production-grade predictive maintenance platform with a Next.js frontend, FastAPI REST backend, real-time MQTT ingestion, ML lifecycle management, RBAC, and local/Docker deployment.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Flow & Pipeline](#3-data-flow--pipeline)
4. [Module Deep Dive](#4-module-deep-dive)
5. [ML Pipeline & Evaluation](#5-ml-pipeline--evaluation)
6. [Database Schema](#6-database-schema)
7. [API Reference](#7-api-reference)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Security & RBAC](#9-security--rbac)
10. [Alerting & Notifications](#10-alerting--notifications)
11. [Deployment](#11-deployment)
12. [Test Suite & Coverage](#12-test-suite--coverage)
13. [Quick Start](#13-quick-start)

---

## 1. Project Overview

### What It Does

The Vehicle Health Monitor ingests **10-channel sensor telemetry** from connected vehicles, trains **5 ML classifiers** to predict failure risk, and presents results through interactive dashboards with **composite health scores**, **SHAP explainability**, **real-time alerts**, and **PDF reporting**.

### The Problem It Solves

Fleet operators lack visibility into vehicle health between scheduled maintenance. This system provides:
- **Real-time anomaly detection** — alerts when sensors exceed thresholds
- **Predictive failure analysis** — ML models estimate failure probability hours/days before breakdown
- **Fleet-wide health aggregation** — see which vehicles need attention at a glance
- **Audit trail** — every alert, model promotion, and sensor reading is logged

### Supported Sensors (10 channels)

| Sensor | Normal Range | Unit | Failure Mode |
|--------|-------------|------|-------------|
| `engine_temp` | 75–105 | °C | Overheating > 130°C |
| `oil_pressure` | 25–65 | psi | Low pressure < 15 psi |
| `coolant_temp` | 75–105 | °C | Overheating > 125°C |
| `engine_rpm` | 600–4500 | RPM | Over-revving > 6000 |
| `vibration` | 0–3.0 | mm/s | Excessive > 5.0 mm/s |
| `fuel_consumption` | 5–15 | L/100km | Abnormal > 25 L/100km |
| `battery_voltage` | 12.4–14.7 | V | Dying < 11.5V |
| `tire_pressure` | 30–35 | psi | Low < 25 psi |
| `speed` | 0–140 | km/h | Excessive > 180 |
| `engine_load` | 10–80 | % | Overloaded > 95% |

### Frontend Strategy

Next.js 14 ── Production website, SSR, premium UI, responsive design, data visualization
```

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS 14 FRONTEND                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  src/app/                                                      │  │
│  │  ├── (auth)/login       Login with JWT                        │  │
│  │  ├── (auth)/register    Registration                           │  │
│  │  ├── (app)/fleet        Fleet overview (landing page)          │  │
│  │  ├── (app)/dashboard    Per-vehicle sensor + health viz        │  │
│  │  ├── (app)/predictions  ML prediction + SHAP explainability    │  │
│  │  ├── (app)/upload       CSV drag-and-drop upload               │  │
│  │  ├── (app)/training     ML model training + comparison         │  │
│  │  ├── (app)/alerts       Alert management + dismiss             │  │
│  │  ├── (app)/history      Maintenance service records            │  │
│  │  └── (app)/reports      PDF download                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Libraries: Next.js 14, Tailwind CSS, Recharts, TanStack Query,     │
│             Zustand, Framer Motion, Axios                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / JSON / WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                               │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Routers (backend/routers/)                                    │  │
│  │  auth │ vehicles │ uploads │ dashboard │ ml │ predictions      │  │
│  │  alerts │ fleet │ recommendations │ reports │ history          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Core (backend/core/)                                          │  │
│  │  config.py — Pydantic Settings from .env                        │  │
│  │  security.py — JWT create/verify (HS256, 8h expiry)            │  │
│  │  dependencies.py — get_current_user, get_db DI                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Shared Python Modules (project root)                           │  │
│  │  db.py ──── SQLAlchemy ORM (8 tables, full CRUD)              │  │
│  │  config.py ── All thresholds, weights, ML params               │  │
│  │  ml_models.py ── 5 classifiers + tuning + drift detection      │  │
│  │  ml_registry.py ── Champion/Challenger versioning              │  │
│  │  preprocessing.py ── Cleaning, feature engineering, labeling   │  │
│  │  health_score.py ── Composite 0-100 health score               │  │
│  │  alerts.py ── Threshold + trend-based alert engine             │  │
│  │  explainability.py ── SHAP Tree/Linear/Kernel explainers       │  │
│  │  recommendations.py ── Rule-based maintenance actions           │  │
│  │  reports.py ── PDF generation via ReportLab                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────────────────────┐
    │              │                              │
    ▼              ▼                              ▼
┌─────────┐  ┌──────────┐  ┌────────────────┐  ┌──────────────┐
│ SQLite  │  │PostgreSQL│  │ Redis          │  │ Mosquitto    │
│ (dev)   │  │(prod)    │  │ (cache +queue) │  │ (MQTT broker)│
└─────────┘  └──────────┘  └────────────────┘  └──────────────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │ OBD-II Sim.  │
                                           │ Fleet Sim.   │
                                           └──────────────┘
```

---

## 3. Data Flow & Pipeline

### End-to-End Flow

```
1. DATA INGESTION
   ┌────────────┐    ┌────────────┐    ┌───────────────┐
   │ CSV Upload  │───►│ Validation │───►│ Preprocessing │
   │ (Next.js)   │    │ (utils.py) │    │ (preproc.py) │
   └────────────┘    └────────────┘    └───────┬───────┘
                                               │
   ┌────────────┐    ┌────────────┐    ┌───────▼───────┐
   │ MQTT Feed  │───►│ Subscriber │───►│ Single Reading│
   │ (Simulator)│    │ (paho)     │    │ Validation    │
   └────────────┘    └────────────┘    └───────┬───────┘
                                               │
                                     ┌─────────▼─────────┐
                                     │  DB: sensor_readings│
                                     └───────────────────┘

2. ML TRAINING (triggered manually or auto-retrain)
   sensor_readings ──► preprocess() ──► train_models() ──► registry.register()
                                                               │
                                                     ┌─────────▼──────────┐
                                                     │ Champion/Challenger │
                                                     │   promotion if     │
                                                     │  F1 improves >2%  │
                                                     └────────────────────┘

3. PREDICTION
   latest reading ──► champion model ──► predict() ──► health_score()
       │                                                    │
       ▼                                                    ▼
   failure_prob + SHAP                               composite 0-100 score
   explanation                                        + health band

4. ALERTING
   sensor value ──► check ALERT_RULES ──► fingerprint dedup ──► DB
       │                                                           │
       ▼                                                           ▼
   escalation (15 min) ──► email / push             incident if 3+ High/hr
```

### Key Data Structures

**Sensor Reading (10 channels + timestamp):**
```python
{
    "timestamp": "2025-06-01T12:00:00",
    "engine_temp": 95.0,       # °C
    "oil_pressure": 40.0,      # psi
    "coolant_temp": 90.0,      # °C
    "engine_rpm": 2000.0,      # RPM
    "vibration": 1.5,          # mm/s
    "fuel_consumption": 8.0,   # L/100km
    "battery_voltage": 13.0,   # V
    "tire_pressure": 32.0,     # psi
    "speed": 60.0,             # km/h
    "engine_load": 40.0,       # %
}
```

**Preprocessing Output (feature-engineered):**
```python
{
    "engine_temp": 95.0,
    "engine_temp_rolling_avg": 93.5,      # 5-period window
    "engine_temp_rate_of_change": -1.2,   # first difference
    "engine_temp_anomaly": 0,             # 1 if outside normal range
    "engine_temp_outlier": 0,             # 1 if IQR outlier
    # ... same for all 10 sensors = ~40 feature columns
    "failure_label": 0,                   # synthetic or user-provided
}
```

---

## 4. Module Deep Dive

### 4.1 `db.py` — Database Layer (738 lines)

**8 ORM Models:**

| Model | Table | Key Columns | Relationships |
|-------|-------|-------------|-------------|
| `User` | `users` | id, username, password_hash, role, organization_id, is_active | → vehicles |
| `Organization` | `organizations` | id, name, plan, max_vehicles | → users |
| `Vehicle` | `vehicles` | id, user_id, vehicle_id_display, model, year, engine_type, mileage | → user, uploads, readings, alerts |
| `SensorUpload` | `sensor_uploads` | id, vehicle_id, user_id, filename, row_count_raw, row_count_clean, preprocessing_log | → readings |
| `SensorReading` | `sensor_readings` | id, upload_id, vehicle_id, user_id, timestamp, 10 sensor cols, failure_label | → upload, vehicle |
| `TrainedModel` | `trained_models` | id, user_id, vehicle_id, model_name, model_version, is_champion, accuracy, f1, roc_auc, feature_columns_json | — |
| `Prediction` | `predictions` | id, user_id, vehicle_id, model_id, prediction, failure_prob, health_score, top_features | → vehicle |
| `Alert` | `alerts` | id, vehicle_id, user_id, alert_type, severity, is_dismissed, acknowledged_at, alert_fingerprint | → vehicle |
| `Incident` | `incidents` | id, vehicle_id, user_id, title, severity, status, related_alert_ids | — |
| `MaintenanceHistory` | `maintenance_history` | id, vehicle_id, user_id, service_date, service_type, cost, notes | → vehicle |
| `Session` | `sessions` | id, user_id, token_hash, expires_at, ip_address | — |
| `AuditLog` | `audit_logs` | id, user_id, action, resource_type, resource_id, details | — |
| `PushSubscription` | `push_subscriptions` | id, user_id, subscription_json | — |
| `NotificationPreferences` | `notification_preferences` | id, user_id, email_enabled, push_enabled, quiet_hours | — |

**Key Indexes:**
```sql
-- Hot-path queries:
ix_sensor_readings_vehicle_timestamp ON sensor_readings (vehicle_id, timestamp)
ix_alerts_user_dismissed             ON alerts (user_id, is_dismissed)
ix_alerts_alert_fingerprint           ON alerts (alert_fingerprint)
```

**Connection Pooling (PostgreSQL):**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### 4.2 `config.py` — Centralized Configuration

All magic numbers in one place:

```python
# Sensor thresholds per channel
SENSOR_THRESHOLDS = {
    "engine_temp": {"min": 75, "max": 105, "critical_min": 50, "critical_max": 130},
    # ... 9 more sensors
}

# Health score formula weights
HEALTH_SCORE_WEIGHTS = {"sensor_health": 0.4, "model_prediction": 0.6}

# ML training parameters
ML_CONFIG = {"test_size": 0.2, "random_state": 42, "min_rows_for_training": 30}

# Alert rules (6 standard + 3 advanced)
ALERT_RULES = {
    "high_engine_temp": {"sensor": "engine_temp", "condition": "above", "threshold": 115},
    "consecutive_high_temp": {"sensor": "engine_temp", "condition": "consecutive_above",
                              "threshold": 105, "consecutive_count": 3},
    "rapid_oil_pressure_drop": {"sensor": "oil_pressure", "condition": "rate_of_change_below",
                                 "threshold": -5.0},
    # ... 7 more rules
}
```

### 4.3 `preprocessing.py` — Data Cleaning Pipeline

**Step-by-step pipeline:**

```
1. Remove duplicates          ──► drop_duplicates()
2. Handle missing values      ──► median imputation, flag if >30% missing
3. Detect outliers (IQR)      ──► flag *_outlier columns (not dropped)
4. Feature engineering        ──► *_rolling_avg, *_rate_of_change, *_anomaly
5. Synthetic labels           ──► failure_label = ≥3 anomalies OR any critical
```

**`preprocess_single_reading()`** — for real-time/MQTT ingestion:
```python
# No DataFrame — validates a single dict
# Maps aliases (rpm → engine_rpm), fills missing with None
# Validates critical ranges, normalizes timestamps
cleaned, errors = preprocess_single_reading(payload)
```

### 4.4 `ml_models.py` — ML Training & Prediction

**5 Classifiers:**
| Model | Hyperparameter Grid | Calibration Support |
|-------|-------------------|-------------------|
| Logistic Regression | `C: [0.01, 10]`, `penalty: [l2]` | sigmoid |
| Decision Tree | `max_depth: [3, None]`, `min_samples_split: [2, 20]` | sigmoid |
| Random Forest | `n_estimators: [50, 200]`, `max_depth: [5, None]` | sigmoid |
| XGBoost | `n_estimators: [50, 200]`, `max_depth: [3, 10]`, `learning_rate: [0.01, 0.3]` | sigmoid |
| SVM | `C: [0.1, 10]`, `kernel: [rbf, linear]` | sigmoid |

**Training Modes:**
```python
# Quick mode — RandomizedSearchCV (limited iterations)
train_models_with_tuning(df, user_id, vehicle_id, tuning_mode="quick")

# Thorough mode — GridSearchCV (exhaustive)
train_models_with_tuning(df, user_id, vehicle_id, tuning_mode="thorough")

# Legacy mode — no hyperparameter search
train_models(df, user_id, vehicle_id)
```

**Model Selection Logic:**
```python
if minority_ratio < 0.2:
    selection_metric = "roc_auc"  # imbalanced classes
else:
    selection_metric = "f1"       # balanced classes
best = max(valid_results, key=lambda r: r["metrics"][selection_metric])
```

### 4.5 `ml_registry.py` — Champion/Challenger

```python
# Register a newly trained model (always as "challenger")
registry.register(model_result, vehicle_id, user_id)

# Promote to champion (demotes all others)
registry.promote_champion(model_id, vehicle_id, user_id)

# Get current champion
champion = registry.get_champion(vehicle_id, user_id)

# List all versions for a vehicle
versions = registry.list_models(vehicle_id, user_id)

# Rollback to previous champion
registry.rollback(vehicle_id, user_id)
```

**Versioning scheme:** `major.minor.0` — auto-increments on each registration.

### 4.6 `health_score.py` — Composite Score

```
health_score = 0.4 × avg_sensor_health + 0.6 × (1 - failure_prob) × 100
```

Per-sensor health computed via linear interpolation between normal and critical bounds:

```
                    ▲ 100 (within normal)
                    │
                    │   linearly decreases
                    │
                    ▼ 0 (at or beyond critical)
```

**Health Bands:**
| Score | Band | Color |
|-------|------|-------|
| 95–100 | Excellent | `#00C851` |
| 80–94 | Good | `#33B5E5` |
| 60–79 | Warning | `#FFBB33` |
| 0–59 | Critical | `#FF4444` |

### 4.7 `explainability.py` — SHAP Explanations

**Explainer Selection:**
```python
if model has feature_importances_:
    explainer = shap.TreeExplainer(model)      # RF, XGB, DT
elif model has coef_:
    explainer = shap.LinearExplainer(model)    # LR
else:
    explainer = shap.KernelExplainer(model)    # SVM fallback
```

**Output:**
```python
{
    "shap_values": np.array([...]),        # raw SHAP values
    "expected_value": 0.32,                # baseline prediction
    "top_features": [
        {"feature": "engine_temp", "contribution_pct": 42.1,
         "description": "Engine Temperature contributed 42% to this prediction"},
        ...
    ],
    "method": "TreeExplainer"
}
```

### 4.8 `alerts.py` — Alert Engine

**Rule Conditions:**
| Condition | Example | Description |
|-----------|---------|-------------|
| `above` | engine_temp > 115°C | Simple threshold |
| `below` | battery_voltage < 12.0V | Simple threshold |
| `consecutive_above` | engine_temp > 105°C × 3 readings | Time-based |
| `rate_of_change_below` | oil_pressure drop > 5 psi/reading | Trend-based |
| `failure_prob_above` | failure_prob > 0.7 | ML-based |

### 4.9 `generate_data.py` — Synthetic Data Generator

**Vehicle Profiles for Simulation:**
```python
generate_realistic_row(vehicle_profile="healthy")           # all sensors normal
generate_realistic_row(vehicle_profile="degrading")          # slow drift
generate_realistic_row(vehicle_profile="critical")           # immediate anomalies
generate_realistic_row(vehicle_profile="intermittent_fault")  # occasional spikes
```

---

## 5. ML Pipeline & Evaluation

### Training Flow

```
                      ┌──────────────────────┐
                      │  get_sensor_readings()│
                      │  (DB → DataFrame)     │
                      └──────────┬───────────┘
                                 ▼
                      ┌──────────────────────┐
                      │  preprocess()         │
                      │  (clean → engineer→   │
                      │   label)              │
                      └──────────┬───────────┘
                                 ▼
                      ┌──────────────────────┐
                      │  get_feature_columns()│
                      │  (~40 cols, no label) │
                      └──────────┬───────────┘
                                 ▼
                      ┌──────────────────────┐
                      │  train_test_split()   │
                      │  (80/20, stratified)  │
                      └──────────┬───────────┘
                                 ▼
                      ┌──────────────────────┐
                      │  StandardScaler()     │
                      │  (fit→transform)      │
                      └──────────┬───────────┘
                                 ▼
            ┌────────────────────┬────────────────────┐
            ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │ GridSearchCV │    │ Randomized   │    │ Default      │
    │ (thorough)   │    │ SearchCV     │    │ Hyperparams  │
    │              │    │ (quick)      │    │              │
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           └──────────────────┼────────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │  CalibratedClassifier │
                    │  CV (sigmoid)         │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  StratifiedKFold CV  │
                    │  (5-fold, scoring)   │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Evaluate on test set │
                    │  (accuracy, precision,│
                    │   recall, f1, auc)    │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Save model .pkl +    │
                    │  scaler .pkl          │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  registry.register()  │
                    │  → versioned model   │
                    └──────────────────────┘
```

### Evaluation Metrics

```python
# Per-model metrics computed on test set:
{
    "accuracy":   round(accuracy_score(y_test, y_pred), 4),
    "precision":  round(precision_score(y_test, y_pred, zero_division=0), 4),
    "recall":     round(recall_score(y_test, y_pred, zero_division=0), 4),
    "f1":         round(f1_score(y_test, y_pred, zero_division=0), 4),
    "roc_auc":    round(roc_auc_score(y_test, y_prob), 4) if y_prob else None,
}
```

**Selection Criteria:**
- Balanced data: **F1 Score** (primary)
- Imbalanced data (< 20% minority): **ROC-AUC** (primary)

**Promotion Criteria:**
- New champion must beat current by **> 2% F1/ROC-AUC** improvement

### Data Drift Detection

```python
# Kolmogorov-Smirnov two-sample test per feature
result = evaluate_drift(reference_df, current_df, alpha=0.05)
# Returns:
{
    "drift_detected": True,           # any feature drifted?
    "drifted_features": ["engine_temp"],  # which features?
    "drift_score": 0.1,               # fraction of drifted features
    "results": {
        "engine_temp": {
            "ks_statistic": 0.25,
            "p_value": 0.001,          # < 0.05 → drifted
            "ref_mean": 90.0,
            "cur_mean": 105.0,
        }
    }
}
```

### Auto-Retrain Trigger

```python
# Celery task — fires when:
def should_retrain(vehicle_id, user_id):
    new_readings > 200 since last training  → True (volume trigger)
    OR drift detected                        → True (distribution trigger)
    OR manual request                        → True
```

---

## 6. Database Schema

### Entity-Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐
│ Organization │       │  User            │
│──────────────│       │──────────────────│
│ id (PK)      │◄──────│ organization_id  │
│ name         │       │ id (PK)          │
│ plan         │       │ username (UQ)    │
│ max_vehicles │       │ password_hash    │
└──────────────┘       │ role             │
                       │ is_active        │
                       └────────┬─────────┘
                                │
               ┌────────────────┼──────────────────┐
               │                │                  │
      ┌────────▼──────┐  ┌─────▼───────┐  ┌───────▼────────┐
      │ Vehicle       │  │ Session     │  │ AuditLog       │
      │───────────────│  │─────────────│  │────────────────│
      │ id (PK)       │  │ token_hash  │  │ action          │
      │ user_id (FK)  │  │ expires_at  │  │ resource_type   │
      │ vehicle_disp  │  │ user_id(FK) │  │ resource_id     │
      │ model         │  └─────────────┘  │ user_id(FK)     │
      └────────┬──────┘                   └─────────────────┘
               │
    ┌──────────┼──────────────────────────────┐
    │          │                              │
┌───▼────┐ ┌──▼─────────┐           ┌─────────▼────────┐
│Upload  │ │Reading     │           │ Alert             │
│─────── │ │─────────── │           │────────────────── │
│id(PK)  │ │ id (PK)    │           │ id (PK)           │
│vehicle │ │ vehicle_id │           │ vehicle_id (FK)   │
│user_id │ │ engine_temp│           │ alert_type        │
│row_cnt │ │ ... 10 cols│           │ severity          │
└────────┘ │ failure_lbl│           │ is_dismissed      │
           └────────────┘           │ alert_fingerprint │
                                    │ acknowledged_at   │
┌──────────────┐    ┌─────────────┐ └───────────────────┘
│ TrainedModel │    │ Prediction  │
│──────────────│    │─────────────│
│ id (PK)      │    │ id (PK)     │
│ model_name   │    │ failure_prob│
│ model_version│    │ health_score│
│ is_champion  │    │ top_features│
│ accuracy     │    │ model_id(FK)│
│ f1 / roc_auc │    │ vehicle(FK) │
│ feature_cols │    └─────────────┘
│ data_hash    │
└──────────────┘
```

---

## 7. API Reference

### Authentication

**POST `/api/v1/auth/register`**
```json
// Request
{ "username": "fleet_mgr", "password": "secure123", "name": "Alice", "email": "alice@fleet.com" }
// Response 200
{ "status": "ok", "detail": "User 'fleet_mgr' created" }
```

**POST `/api/v1/auth/login`**
```json
// Request
{ "username": "fleet_mgr", "password": "secure123" }
// Response 200
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer",
  "user_id": 1, "username": "fleet_mgr", "role": "admin" }
```

### Vehicles

**GET `/api/v1/vehicles`** — List all vehicles for authenticated user
```json
// Response 200
[{ "id": 1, "vehicle_id_display": "VH-001", "model": "Toyota Camry", "manufacturing_year": 2025 }]
```

**POST `/api/v1/vehicles`** — Register a new vehicle
```json
// Request
{ "vehicle_id_display": "VH-002", "model": "Honda Civic", "manufacturing_year": 2024, "engine_type": "Hybrid" }
```

### Dashboard

**GET `/api/v1/dashboard/{vehicle_id}`** — Aggregated dashboard data
```json
// Response 200
{
  "vehicle": { "id": 1, "vehicle_id_display": "VH-001" },
  "health_score": 82.5,
  "health_band": "Good",
  "active_alerts": 1,
  "total_readings": 450,
  "recent_readings": [{ "id": 1, "engine_temp": 95.0, "timestamp": "..." }]
}
```

### ML Training

**POST `/api/v1/ml/train/{vehicle_id}?tuning_mode=quick`** — Start async training
```json
// Response 202
{ "job_id": "a1b2c3d4", "status": "started" }
```

**GET `/api/v1/ml/train/status/{job_id}`** — Poll training status
```json
// Response 200 (in progress)
{ "job_id": "a1b2c3d4", "status": "running", "result": null }
// Response 200 (complete)
{ "job_id": "a1b2c3d4", "status": "complete", "result": { "best_model": "XGBoost", ... } }
```

### Predictions

**POST `/api/v1/predictions/run/{vehicle_id}`** — Run failure prediction
```json
// Response 200
{
  "prediction_id": 42,
  "prediction_class": "Needs Maintenance Soon",
  "failure_prob": 0.62,
  "confidence": 0.62,
  "prediction_icon": "WARN",
  "prediction_color": "#d97706",
  "top_features": [
    { "feature": "engine_temp_anomaly", "importance": 0.35 },
    { "feature": "vibration", "importance": 0.22 }
  ]
}
```

### Data Upload

**POST `/api/v1/uploads/{vehicle_id}`** — Upload CSV (multipart/form-data)
```json
// Response 201
{
  "upload_id": 15,
  "row_count_raw": 500,
  "row_count_clean": 498,
  "log_entries": ["**Duplicates:** Removed 2 duplicate rows", "**Missing Values:** No missing...", "..."],
  "preview": [{ "engine_temp": 95.0, "timestamp": "..." }]
}
```

### Alerts

**GET `/api/v1/alerts/{vehicle_id}?active_only=true`**
```json
[{ "id": 1, "alert_type": "high_engine_temp", "severity": "High",
   "message": "Engine temperature is critically high (125 deg C)!", "created_at": "..." }]
```

**PATCH `/api/v1/alerts/{alert_id}/dismiss`**
```json
{ "status": "ok", "detail": "Alert dismissed" }
```

### Fleet

**GET `/api/v1/fleet/overview`**
```json
{
  "vehicle_count": 5,
  "avg_health_score": 78.3,
  "healthy_count": 3,
  "at_risk_count": 1,
  "critical_count": 1,
  "total_active_alerts": 4
}
```

### Reports

**GET `/api/v1/reports/{vehicle_id}/pdf`** — Returns application/pdf binary stream

---

## 8. Frontend Architecture (Next.js)

### Component Hierarchy

```
src/app/layout.tsx                    ← Root: fonts, metadata, QueryProvider
├── src/app/(auth)/layout.tsx        ← Auth layout (no sidebar)
│   ├── login/page.tsx               ← Split-screen login
│   └── register/page.tsx            ← Registration form
│
└── src/app/(app)/layout.tsx         ← App shell (requires auth)
    ├── Sidebar.tsx                  ← Navigation (8 routes)
    ├── Topbar.tsx                   ← User menu, vehicle selector
    └── Pages:
        ├── fleet/page.tsx           ← KPI cards, distribution, vehicle list
        ├── dashboard/[vehicleId]    ← Health gauge, sensor summary, trend charts, alerts
        ├── upload/[vehicleId]       ← CSV drag-and-drop
        ├── training/[vehicleId]     ← Model training + comparison
        ├── predictions/[vehicleId]  ← Prediction result, feature importance, history
        ├── recommendations/[vehicleId] ← Alerts list
        ├── history/[vehicleId]      ← Maintenance timeline
        └── reports/[vehicleId]      ← PDF download
```

### State Management

```typescript
// Zustand — auth + session state (persisted to localStorage)
interface AuthState {
  token: string | null;
  user: { id: number; username: string; role: string } | null;
  selectedVehicleId: number | null;
  setAuth(token, user): void;
  logout(): void;
}

// TanStack Query — server state (auto-cached, background refetch)
useDashboard(vehicleId)   // refetchInterval: 30s
useAlerts(vehicleId)      // refetchInterval: 15s
useFleet()                // refetchInterval: 30s
useVehicles()
usePredictions(vehicleId)
```

### API Client

```typescript
// Axios instance with JWT interceptor
api.interceptors.request.use((config) => {
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) logout();
  }
);
```

### Design Tokens

```css
--bg-base: #080d14;           /* near-black navy */
--bg-surface: #0f1924;        /* card backgrounds */
--bg-elevated: #162030;       /* hover states */
--border: #1e3047;            /* subtle borders */
--accent-sky: #0ea5e9;        /* primary brand */
--accent-green: #10b981;      /* health/good */
--accent-amber: #f59e0b;      /* warning */
--accent-red: #ef4444;        /* critical */
--text-primary: #f0f6ff;      /* main text */
--text-muted: #8da4c4;        /* muted text */
```

---

## 9. Security & RBAC

### Role Hierarchy

```
admin (most privileged)
  └── fleet_manager
        └── technician
              └── driver (least privileged)
```

### Permission Matrix

| Permission | admin | fleet_manager | technician | driver |
|------------|-------|---------------|------------|--------|
| `view_own_vehicle` | ✅ | ✅ | ✅ | ✅ |
| `view_own_alerts` | ✅ | ✅ | ✅ | ✅ |
| `view_vehicles` | ✅ | ✅ | ✅ | — |
| `view_alerts` | ✅ | ✅ | ✅ | — |
| `update_maintenance` | ✅ | ✅ | ✅ | — |
| `view_predictions` | ✅ | ✅ | ✅ | — |
| `manage_vehicles` | ✅ | ✅ | — | — |
| `manage_alerts` | ✅ | ✅ | — | — |
| `export_data` | ✅ | ✅ | — | — |
| `manage_users` | ✅ | — | — | — |
| `manage_models` | ✅ | — | — | — |
| `delete_vehicles` | ✅ | — | — | — |
| `view_audit_logs` | ✅ | — | — | — |

### Session Management

```python
# JWT-based / DB-backed tokens (Next.js)
SESSION_TTL = 8 hours
create_session(user_id)     → token string
validate_session(token)     → user dict or None
invalidate_session(token)   → logout
```

### Audit Trail

All critical actions logged to `audit_logs`:
```python
log_audit(user_id, action="model_promoted", resource_type="TrainedModel", resource_id=42)
log_audit(user_id, action="vehicle_deleted", resource_type="Vehicle", resource_id=7)
log_audit(user_id, action="alert_dismissed", resource_type="Alert", resource_id=15)
```

---

## 10. Alerting & Notifications

### Alert Flow

```
Sensor Reading ──► Alert Rules Check
                        │
                ┌───────┴───────┐
                │               │
           triggered        not triggered
                │               │
          fingerprint         skip
          dedup (30min)
                │
        ┌───────┴───────┐
        │               │
    duplicate        new alert
        │               │
      skip         ┌────┴────┐
                   │         │
               DB save   notification
                   │
             ┌─────┴──────┐
             │            │
        escalation    email/push
        (15 min)      delivery
             │
        ┌────┴────┐
        │         │
    incident     SMS
    (3+/hr)     (Twilio)
```

### Notification Channels

| Channel | Transport | Config Required | Status |
|---------|-----------|----------------|--------|
| Email | SMTP (Gmail/SendGrid) | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | ✅ |
| Browser Push | Web Push (VAPID) | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | ✅ (stub) |
| SMS | Twilio | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | 🔧 (planned) |
| In-app | WebSocket | Automatic | ✅ |

### Escalation Rules

```python
# Rule 1: High alert unacknowledged for 15+ minutes → email
pending = get_unacknowledged_high_alerts(user_id, vehicle_id, since_minutes=15)

# Rule 2: 3+ High alerts in 1 hour → auto-create incident ticket
count = count_alerts_last_hour(vehicle_id, user_id)
if count >= 3:
    incident = create_incident(vehicle_id, user_id, title="...")
```

---

## 11. Deployment

### Docker Compose Topology

```yaml
services:
  postgres:     # PostgreSQL 16 (persistent storage)
  redis:        # Redis 7 (cache + Celery broker)
  mosquitto:    # MQTT broker (OBD-II ingestion)
  api:          # FastAPI backend (uvicorn)
  celery-worker:# Celery auto-retrain worker
  mqtt-subscriber: # MQTT → DB subscriber
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    services:
      postgres: # PostgreSQL 16 container
    steps:
      - pip install -r requirements.txt
      - ruff check .
      - pytest tests/ -v --cov=. --cov-fail-under=70
  docker:
    needs: test
    - docker compose build
```

### Health Checks

```
GET /health → { status: "ok", database: "connected" }
GET /metrics → Prometheus-format metrics (if prometheus_client installed)
```

---

## 12. Test Suite & Coverage

### Test Modules (200+ tests)

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_preprocessing.py` | 18 | Duplicate removal, imputation, outliers, feature engineering, labels |
| `test_health_score.py` | 18 | Sensor scoring, composite formula, fleet aggregation |
| `test_ml_models.py` | 19 | Training, prediction, CV scores, drift detection, calibration |
| `test_ml_registry.py` | 9 | Registration, champion promotion, rollback, versioning |
| `test_alerts.py` | 17 | Alert rules, dedup, maintenance overdue, severity helpers |
| `test_db.py` | 20 | All CRUD operations across 7 models |
| `test_ingestion.py` | 17 | Realistic row generation, single-reading validation |
| `test_notifications.py` | 16 | Escalation, email/push stubs, incidents, preferences |
| `test_rbac.py` | 21 | Permissions, sessions, orgs, user management, audit logs |
| `test_monitoring.py` | 5 | Health checks, DB size, stub metrics |
| `test_api.py` | 12 | FastAPI endpoints, auth, CRUD, validation |

**Coverage:** ~66% overall (core modules >90%)

### Test Fixtures

```python
# conftest.py provides:
db_session   → isolated SQLite DB (resets per test)
test_user    → seeded user with known credentials
test_vehicle → vehicle linked to test_user
sample_sensor_data → 50-row clean DataFrame
sample_sensor_data_with_anomalies → 30 rows with known failure patterns
```

---

## 13. Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for Next.js frontend)
- Docker (for production deployment)

### Start the Application

```bash
# Install backend dependencies & setup database
python -m venv .venv && source .venv/bin/activate
cp .env.example .env
pip install -r requirements.txt
alembic upgrade head
python generate_data.py

# Start Backend API (runs on port 8000)
make api

# Start Next.js Frontend (runs on port 3000 - in a separate terminal)
make run
```

### OBD-II Simulator

```bash
# Single vehicle
python simulator/obd_simulator.py --vehicle-id VH-001 --interval 5 --profile healthy

# Fleet (5 vehicles)
make fleet

# Subscribe to MQTT feed
python ingest/mqtt_subscriber.py
```

### Test

```bash
make test  # or: pytest tests/ -v --cov=.
```

### Docker

```bash
make docker-up  # Start all services
make docker-down  # Stop all
```

---

*Generated from the Vehicle Health Monitor codebase. Last updated: 2026-07-08.*
