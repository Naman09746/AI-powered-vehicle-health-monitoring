"""
Custom OpenAPI 3.1 schema generation for the Vehicle Health Monitor API.

Enriches the auto-generated OpenAPI spec with:
- Server URLs for dev, staging, and production
- External documentation links
- Contact and license information
- Tag descriptions for all route groups
- Example values on Pydantic schemas
- ``x-logo`` extension for API docs branding
- Customised ``operationId`` naming
- Response examples for 2xx, 4xx, and 5xx responses
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

# ── Tag descriptions ──────────────────────────────────────────────

TAG_DESCRIPTIONS: dict[str, str] = {
    "health": "Liveness and readiness probes for container orchestration and monitoring.",
    "auth": "User authentication — login, register, and session management.",
    "api-keys": "API key management for machine-to-machine authentication.",
    "vehicles": "Vehicle CRUD — register, list, and retrieve vehicle details.",
    "readings": "Sensor data ingestion and retrieval for vehicle telemetry.",
    "predictions": "ML-driven failure predictions — run and retrieve results.",
    "alerts": "Alert management — list, acknowledge, and dismiss threshold-based alerts.",
    "reports": "PDF report generation for vehicle health summaries.",
    "ml": "ML model lifecycle — train, list, promote champion/challenger models.",
    "uploads": "CSV file ingestion for batch sensor data uploads.",
    "dashboard": "Aggregated dashboard data with SSE streaming for real-time updates.",
    "fleet": "Fleet-wide aggregated health overview across all vehicles.",
    "history": "Maintenance history CRUD — service records for each vehicle.",
    "recommendations": "Actionable recommendations combining alerts, deviations, and predictions.",
    "simulator": "Live sensor data simulation for testing and demonstration.",
    "webhooks": "Webhook subscription management and async event delivery.",
}


# ── API servers ───────────────────────────────────────────────────

API_SERVERS: list[dict[str, str]] = [
    {"url": "http://localhost:8000", "description": "Local development"},
    {"url": "https://api.staging.vehiclehealth.example.com", "description": "Staging"},
    {"url": "https://api.vehiclehealth.example.com", "description": "Production"},
]


# ── Response examples ─────────────────────────────────────────────

RESPONSE_EXAMPLES: dict[str, dict[str, Any]] = {
    "200": {
        "description": "Successful response",
        "content": {
            "application/json": {
                "example": {
                    "status": "ok",
                    "data": {},
                    "meta": {"request_id": "abc-123-def-456"},
                }
            }
        },
    },
    "400": {
        "description": "Bad request — invalid input or missing parameters",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/400",
                    "title": "Bad Request",
                    "status": 400,
                    "detail": "No sensor data available for the specified vehicle.",
                    "instance": "/api/v1/ml/train/42",
                }
            }
        },
    },
    "401": {
        "description": "Unauthorized — missing or invalid authentication credentials",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/401",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": "Missing Authorization header (Bearer <token>)",
                    "instance": "/api/v1/vehicles",
                }
            }
        },
    },
    "403": {
        "description": "Forbidden — insufficient permissions for the requested resource",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/403",
                    "title": "Forbidden",
                    "status": 403,
                    "detail": "You do not have access to this resource.",
                    "instance": "/api/v1/fleet/overview",
                }
            }
        },
    },
    "404": {
        "description": "Resource not found",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/404",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "The requested resource '/api/v1/vehicles/999' was not found",
                    "instance": "/api/v1/vehicles/999",
                }
            }
        },
    },
    "409": {
        "description": "Conflict — resource already exists",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/409",
                    "title": "Conflict",
                    "status": 409,
                    "detail": "Vehicle 'TRUCK-001' already exists",
                    "instance": "/api/v1/vehicles",
                }
            }
        },
    },
    "422": {
        "description": "Unprocessable Entity — request validation failed",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/422",
                    "title": "Unprocessable Entity",
                    "status": 422,
                    "detail": "Request validation failed",
                    "instance": "/api/v1/vehicles",
                    "errors": [
                        {
                            "field": "body -> vehicle_id_display",
                            "message": "field required",
                            "type": "missing",
                        },
                        {
                            "field": "body -> manufacturing_year",
                            "message": "ensure this value is less than or equal to 2030",
                            "type": "value_error",
                        },
                    ],
                }
            }
        },
    },
    "429": {
        "description": "Too Many Requests — rate limit exceeded",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/429",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "Rate limit exceeded: 120 requests per minute",
                    "instance": "/api/v1/vehicles",
                }
            }
        },
    },
    "500": {
        "description": "Internal server error",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/500",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "An unexpected error occurred",
                    "instance": "/api/v1/ml/train/42",
                }
            }
        },
    },
    "502": {
        "description": "Bad Gateway — upstream service unavailable",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/502",
                    "title": "Bad Gateway",
                    "status": 502,
                    "detail": "Upstream ML service returned an error",
                    "instance": "/api/v1/predictions/run",
                }
            }
        },
    },
    "503": {
        "description": "Service Unavailable — temporary maintenance or overload",
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://httpstatuses.org/503",
                    "title": "Service Unavailable",
                    "status": 503,
                    "detail": "Database connection pool exhausted. Retry later.",
                    "instance": "/api/v1/dashboard/1",
                }
            }
        },
    },
}


def _custom_operation_id(route: APIRoute) -> str:
    """
    Generate a short, predictable ``operationId`` for each route.

    Format: ``{tag}_{method}_{name}`` where *name* is the last non-param
    path segment.  Falls back to the route's endpoint ``__name__``.
    """
    tag = route.tags[0] if route.tags else "default"
    method = route.methods.pop() if route.methods else "ANY"
    method = method.lower()

    # Extract a short name from the path
    parts = [p for p in route.path.split("/") if p and not p.startswith("{")]
    name = parts[-1] if parts else "root"

    return f"{tag}_{method}_{name}"


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """
    Build a custom OpenAPI 3.1 schema for the application.

    Call this from the app's ``openapi`` function or set
    ``app.openapi = custom_openapi`` during startup.

    Features:
    - Overrides the default ``operationId`` with a clean tag-based scheme.
    - Injects server URLs, external docs, contact, and license info.
    - Attaches human-readable descriptions to every tag.
    - Adds ``x-logo`` branding extension.
    - Embeds response examples for common HTTP status codes.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # ── OpenAPI 3.1 bump ──────────────────────────────────────────
    openapi_schema["openapi"] = "3.1.0"

    # ── Servers ──────────────────────────────────────────────────
    openapi_schema["servers"] = API_SERVERS

    # ── Info ──────────────────────────────────────────────────────
    openapi_schema["info"] = {
        **openapi_schema.get("info", {}),
        "contact": {
            "name": "Vehicle Health Monitor Support",
            "email": "support@vehiclehealth.example.com",
            "url": "https://vehiclehealth.example.com/support",
        },
        "license": {
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
    }

    # ── External docs ─────────────────────────────────────────────
    openapi_schema["externalDocs"] = {
        "description": "Vehicle Health Monitor Documentation",
        "url": "https://docs.vehiclehealth.example.com",
    }

    # ── Tag descriptions ─────────────────────────────────────────
    tag_descriptions = []
    seen_tags: set[str] = set()
    for tag_name, desc in TAG_DESCRIPTIONS.items():
        tag_descriptions.append({"name": tag_name, "description": desc})
        seen_tags.add(tag_name)

    # Include any tags used by routes that aren't in our predefined list
    for route in app.routes:
        if hasattr(route, "tags"):
            for tag in route.tags:
                if tag not in seen_tags:
                    tag_descriptions.append(
                        {"name": tag, "description": f"Routes grouped under ``{tag}``."}
                    )
                    seen_tags.add(tag)

    openapi_schema["tags"] = tag_descriptions

    # ── x-logo branding ──────────────────────────────────────────
    openapi_schema.setdefault("info", {})["x-logo"] = {
        "url": "https://vehiclehealth.example.com/logo.png",
        "altText": "Vehicle Health Monitor",
        "backgroundColor": "#1a202c",
    }

    # ── Custom operationId ────────────────────────────────────────
    if "paths" in openapi_schema:
        for path, methods in openapi_schema["paths"].items():
            for method, operation in methods.items():
                if isinstance(operation, dict):
                    # Map route to operationId via path lookup
                    operation["operationId"] = _build_operation_id(path, method)

    # ── Response examples ─────────────────────────────────────────
    if "paths" in openapi_schema:
        for path, methods in openapi_schema["paths"].items():
            for method, operation in methods.items():
                if isinstance(operation, dict) and "responses" in operation:
                    _inject_response_examples(operation["responses"])

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def _build_operation_id(path: str, method: str) -> str:
    """Build a clean operationId from path + method."""
    method = method.lower()
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if parts:
        return "_".join([method, *parts])
    return f"{method}_root"


def _inject_response_examples(responses: dict[str, Any]) -> None:
    """Attach example bodies to common HTTP response codes."""
    for status_code, example in RESPONSE_EXAMPLES.items():
        if status_code in responses:
            existing = responses[status_code]
            # Only inject if the route doesn't already define its own content
            for media_type, example_body in example.get("content", {}).items():
                if media_type not in existing.get("content", {}):
                    existing.setdefault("content", {})[media_type] = example_body
