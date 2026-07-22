"""
Centralized configuration for the Predictive Maintenance system.
All thresholds, weights, sensor ranges, and magic numbers live here.

Secrets and environment-specific values are loaded from .env via python-dotenv.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load .env from project root
# ──────────────────────────────────────────────
_env_path = Path(__file__).with_name(".env")
if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Fallback: try parent directories (useful for tests)
    _candidate = Path.cwd() / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)

# ──────────────────────────────────────────────
# Environment & secrets
# ──────────────────────────────────────────────
ENV = os.getenv("ENV", "development")  # development | production
SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-key-change-in-production")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "200"))
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8501,http://localhost:8000,https://ai-powered-vehicle-health-monitorin.vercel.app",
)
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in _raw_origins.split(",")
    if origin.strip()
]


# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
# SQLite (dev):   sqlite:///vehicle_health.db
# PostgreSQL:     postgresql://user:password@host:5432/vehicle_health
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///vehicle_health.db")

# ──────────────────────────────────────────────
# Read replica database (optional, for dashboard queries)
# ──────────────────────────────────────────────
DATABASE_URL_READ_ONLY = os.getenv("DATABASE_URL_READ_ONLY", "")

# ──────────────────────────────────────────────
# SMTP / Email
# ──────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Vehicle Health Monitor <alerts@yourdomain.com>")

# ──────────────────────────────────────────────
# Redis / Celery
# ──────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ──────────────────────────────────────────────
# MLflow tracking
# ──────────────────────────────────────────────
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_S3_ENDPOINT_URL = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000")
MLFLOW_EXPERIMENT_NAME_PREFIX = os.getenv(
    "MLFLOW_EXPERIMENT_NAME_PREFIX", "vehicle_health"
)

# MinIO / S3 credentials for MLflow artifact storage
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

# ──────────────────────────────────────────────
# OpenTelemetry
# ──────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
)

# ──────────────────────────────────────────────
# Keycloak / OAuth2
# ──────────────────────────────────────────────
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "vehicle-health")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "vhm-api")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
OAUTH_ENABLED = os.getenv("OAUTH_ENABLED", "false").lower() == "true"

# ──────────────────────────────────────────────
# Session management
# ──────────────────────────────────────────────
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "8"))
MAX_REFRESH_COUNT = int(os.getenv("MAX_REFRESH_COUNT", "10"))

# ──────────────────────────────────────────────
# Twilio SMS
# ──────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# ──────────────────────────────────────────────
# Web Push / VAPID
# ──────────────────────────────────────────────
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "")

# ──────────────────────────────────────────────
# Sensor normal operating ranges & thresholds
# ──────────────────────────────────────────────
SENSOR_THRESHOLDS = {
    "engine_temp": {
        "min": 75,
        "max": 105,
        "critical_min": 50,
        "critical_max": 130,
        "unit": "deg C",
        "label": "Engine Temperature",
    },
    "oil_pressure": {
        "min": 25,
        "max": 65,
        "critical_min": 15,
        "critical_max": 80,
        "unit": "psi",
        "label": "Oil Pressure",
    },
    "coolant_temp": {
        "min": 75,
        "max": 105,
        "critical_min": 50,
        "critical_max": 125,
        "unit": "deg C",
        "label": "Coolant Temperature",
    },
    "engine_rpm": {
        "min": 600,
        "max": 4500,
        "critical_min": 300,
        "critical_max": 6000,
        "unit": "RPM",
        "label": "Engine RPM",
    },
    "vibration": {
        "min": 0.0,
        "max": 3.0,
        "critical_min": 0.0,
        "critical_max": 5.0,
        "unit": "mm/s",
        "label": "Vibration",
    },
    "fuel_consumption": {
        "min": 5.0,
        "max": 15.0,
        "critical_min": 2.0,
        "critical_max": 25.0,
        "unit": "L/100km",
        "label": "Fuel Consumption",
    },
    "battery_voltage": {
        "min": 12.4,
        "max": 14.7,
        "critical_min": 11.5,
        "critical_max": 15.5,
        "unit": "V",
        "label": "Battery Voltage",
    },
    "tire_pressure": {
        "min": 30,
        "max": 35,
        "critical_min": 25,
        "critical_max": 40,
        "unit": "psi",
        "label": "Tire Pressure",
    },
    "speed": {
        "min": 0,
        "max": 140,
        "critical_min": 0,
        "critical_max": 180,
        "unit": "km/h",
        "label": "Speed",
    },
    "engine_load": {
        "min": 10,
        "max": 80,
        "critical_min": 0,
        "critical_max": 95,
        "unit": "%",
        "label": "Engine Load",
    },
}

# Ordered list of sensor columns (used for validation, iteration, etc.)
SENSOR_COLUMNS = list(SENSOR_THRESHOLDS.keys())

# Required columns in uploaded CSV
REQUIRED_COLUMNS = {"timestamp"} | set(SENSOR_COLUMNS)

# Column alias map - common alternative names to canonical names
COLUMN_ALIASES = {
    "engine_temperature": "engine_temp",
    "eng_temp": "engine_temp",
    "coolant_temperature": "coolant_temp",
    "cool_temp": "coolant_temp",
    "rpm": "engine_rpm",
    "eng_rpm": "engine_rpm",
    "vib": "vibration",
    "fuel_cons": "fuel_consumption",
    "fuel": "fuel_consumption",
    "bat_voltage": "battery_voltage",
    "battery_volt": "battery_voltage",
    "battery": "battery_voltage",
    "tire_press": "tire_pressure",
    "tyre_pressure": "tire_pressure",
    "eng_load": "engine_load",
    "load": "engine_load",
    "spd": "speed",
    "vehicle_speed": "speed",
    "ts": "timestamp",
    "time": "timestamp",
    "datetime": "timestamp",
    "date": "timestamp",
}

# ──────────────────────────────────────────────
# Health score configuration
# ──────────────────────────────────────────────
HEALTH_SCORE_WEIGHTS = {
    "sensor_health": 0.4,
    "model_prediction": 0.6,
}

HEALTH_BANDS = {
    "Excellent": {"min": 95, "max": 100, "color": "#00C851"},
    "Good": {"min": 80, "max": 94, "color": "#33B5E5"},
    "Warning": {"min": 60, "max": 79, "color": "#FFBB33"},
    "Critical": {"min": 0, "max": 59, "color": "#FF4444"},
}

# ──────────────────────────────────────────────
# Failure prediction & priority
# ──────────────────────────────────────────────
FAILURE_CLASSES = {
    "healthy": {"label": "Healthy", "max_prob": 0.4, "color": "#16a34a", "icon": "OK"},
    "maintenance": {
        "label": "Needs Maintenance Soon",
        "max_prob": 0.7,
        "color": "#d97706",
        "icon": "WARN",
    },
    "high_risk": {
        "label": "High Risk of Failure",
        "max_prob": 1.0,
        "color": "#dc2626",
        "icon": "RISK",
    },
}

PRIORITY_THRESHOLDS = {
    "Low": 0.4,  # failure_prob < 0.4
    "Medium": 0.7,  # 0.4 <= failure_prob < 0.7
    "High": 1.0,  # failure_prob >= 0.7
}

# ──────────────────────────────────────────────
# Synthetic labeling rules
# ──────────────────────────────────────────────
# Minimum number of anomalous sensors to trigger failure label
SYNTHETIC_LABEL_MIN_ANOMALIES = 3

# ──────────────────────────────────────────────
# ML configuration
# ──────────────────────────────────────────────
ML_CONFIG = {
    "test_size": 0.2,
    "random_state": 42,
    "min_rows_for_training": 30,
    "imbalance_threshold": 0.2,  # minority class < 20%, use ROC-AUC for selection
}

# Model hyperparameters
MODEL_PARAMS = {
    "LogisticRegression": {"max_iter": 1000, "random_state": 42},
    "DecisionTree": {"max_depth": 10, "random_state": 42},
    "RandomForest": {"n_estimators": 100, "max_depth": 15, "random_state": 42},
    "XGBoost": {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "random_state": 42,
        "use_label_encoder": False,
        "eval_metric": "logloss",
    },
    "SVM": {"probability": True, "kernel": "rbf", "random_state": 42},
}

# ──────────────────────────────────────────────
# Preprocessing
# ──────────────────────────────────────────────
PREPROCESSING = {
    "missing_value_threshold": 0.3,  # flag if >30% missing
    "outlier_method": "iqr",  # "iqr" or "zscore"
    "iqr_multiplier": 1.5,
    "zscore_threshold": 3.0,
    "rolling_window": 5,
}

# ──────────────────────────────────────────────
# Maintenance recommendations mapping
# ──────────────────────────────────────────────
RECOMMENDATION_RULES = {
    "engine_temp": {
        "condition": "high",
        "action": "Engine service / coolant system inspection",
        "description": "Engine temperature is above safe operating range.",
    },
    "oil_pressure": {
        "condition": "low",
        "action": "Oil change / oil pump inspection",
        "description": "Oil pressure has dropped below safe levels.",
    },
    "coolant_temp": {
        "condition": "high",
        "action": "Coolant refill / radiator inspection",
        "description": "Coolant temperature is elevated, risk of overheating.",
    },
    "battery_voltage": {
        "condition": "low",
        "action": "Battery replacement / alternator check",
        "description": "Battery voltage is low, may fail to start.",
    },
    "vibration": {
        "condition": "high",
        "action": "Brake inspection / wheel alignment / bearing check",
        "description": "Excessive vibration detected in the drivetrain.",
    },
    "tire_pressure": {
        "condition": "low",
        "action": "Tire inflation / tire replacement",
        "description": "Tire pressure is below recommended levels.",
    },
    "fuel_consumption": {
        "condition": "high",
        "action": "Fuel system / injector service",
        "description": "Fuel consumption is abnormally high.",
    },
    "engine_load": {
        "condition": "high",
        "action": "Engine diagnostics / load reduction",
        "description": "Engine is operating under excessive load.",
    },
    "engine_rpm": {
        "condition": "high",
        "action": "Transmission / throttle body inspection",
        "description": "Engine RPM is consistently elevated.",
    },
}

# Priority to recommended service window (days from now)
PRIORITY_SERVICE_WINDOWS = {
    "High": 0,  # ASAP / immediate
    "Medium": 14,  # within 2 weeks
    "Low": 30,  # within 30 days
}

# ──────────────────────────────────────────────
# Alert thresholds (for real-time alerting)
# ──────────────────────────────────────────────
ALERT_RULES = {
    "high_engine_temp": {
        "sensor": "engine_temp",
        "condition": "above",
        "threshold": 115,
        "severity": "High",
        "message": "Engine temperature is critically high ({value} deg C)!",
    },
    "low_battery": {
        "sensor": "battery_voltage",
        "condition": "below",
        "threshold": 12.0,
        "severity": "High",
        "message": "Battery voltage is critically low ({value}V)!",
    },
    "low_oil_pressure": {
        "sensor": "oil_pressure",
        "condition": "below",
        "threshold": 20,
        "severity": "High",
        "message": "Oil pressure dangerously low ({value} psi)!",
    },
    "high_vibration": {
        "sensor": "vibration",
        "condition": "above",
        "threshold": 4.0,
        "severity": "Medium",
        "message": "Abnormal vibration detected ({value} mm/s).",
    },
    "low_tire_pressure": {
        "sensor": "tire_pressure",
        "condition": "below",
        "threshold": 27,
        "severity": "Medium",
        "message": "Tire pressure is low ({value} psi).",
    },
    "high_failure_risk": {
        "sensor": None,
        "condition": "failure_prob_above",
        "threshold": 0.7,
        "severity": "High",
        "message": "Model predicts HIGH failure risk ({value:.0%})!",
    },
    # ── Phase 5: Time-based rules ──
    "consecutive_high_temp": {
        "sensor": "engine_temp",
        "condition": "consecutive_above",
        "threshold": 105,
        "consecutive_count": 3,
        "severity": "High",
        "message": "Engine temperature above 105°C for 3 consecutive readings!",
    },
    "rapid_oil_pressure_drop": {
        "sensor": "oil_pressure",
        "condition": "rate_of_change_below",
        "threshold": -5.0,
        "severity": "High",
        "message": "Oil pressure dropping rapidly ({value} psi/reading)!",
    },
    "low_coolant_temp": {
        "sensor": "coolant_temp",
        "condition": "below",
        "threshold": 70,
        "severity": "Medium",
        "message": "Coolant temperature is low ({value} deg C).",
    },
}

# ──────────────────────────────────────────────
# App UI settings
# ──────────────────────────────────────────────
APP_CONFIG = {
    "page_title": "Vehicle Health Monitor",
    "page_icon": "VH",
    "layout": "wide",
}
