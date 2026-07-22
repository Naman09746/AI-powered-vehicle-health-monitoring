"""LLM-powered maintenance copilot (AF-09). Generates analyzer reports from sensor data."""

from __future__ import annotations

from typing import Any

from core.config import SENSOR_THRESHOLDS
from core.logger import get_logger

log = get_logger("ml.copilot")


def analyze_vehicle_health(
    vehicle_info: dict,
    recent_readings: list[dict],
    predictions: list[dict] | None = None,
    alerts: list[dict] | None = None,
) -> dict[str, Any]:
    """Generate a structured health analysis from sensor data.

    No LLM required — uses rule-based analysis with plain-language output.
    """
    issues = []
    summary_parts = []

    if not recent_readings:
        return {
            "summary": "No sensor data available for analysis.",
            "issues": [],
            "recommendations": [],
        }

    latest = recent_readings[-1] if recent_readings else {}

    # Check each sensor against thresholds
    for sensor, cfg in SENSOR_THRESHOLDS.items():
        val = latest.get(sensor)
        if val is None:
            continue
        if val > cfg["critical_max"]:
            issues.append(
                {
                    "severity": "critical",
                    "sensor": cfg["label"],
                    "value": val,
                    "message": f"{cfg['label']} critically high ({val:.1f} {cfg['unit']}). Immediate inspection required.",
                }
            )
        elif val < cfg["critical_min"]:
            issues.append(
                {
                    "severity": "critical",
                    "sensor": cfg["label"],
                    "value": val,
                    "message": f"{cfg['label']} critically low ({val:.1f} {cfg['unit']}). Immediate inspection required.",
                }
            )
        elif val > cfg["max"]:
            issues.append(
                {
                    "severity": "warning",
                    "sensor": cfg["label"],
                    "value": val,
                    "message": f"{cfg['label']} above normal range ({val:.1f} {cfg['unit']}). Monitor closely.",
                }
            )
        elif val < cfg["min"]:
            issues.append(
                {
                    "severity": "warning",
                    "sensor": cfg["label"],
                    "value": val,
                    "message": f"{cfg['label']} below normal range ({val:.1f} {cfg['unit']}). Schedule inspection.",
                }
            )

    # Trending analysis (last N readings)
    if len(recent_readings) >= 5:
        window = recent_readings[-5:]
        for sensor, cfg in SENSOR_THRESHOLDS.items():
            vals = [r.get(sensor) for r in window if r.get(sensor) is not None]
            if len(vals) < 3:
                continue
            trend = (vals[-1] - vals[0]) / vals[0] if vals[0] else 0
            if abs(trend) > 0.15:
                direction = "rising" if trend > 0 else "falling"
                issues.append(
                    {
                        "severity": "info",
                        "sensor": cfg["label"],
                        "trend_pct": round(trend * 100, 1),
                        "message": f"{cfg['label']} {direction} ({trend * 100:.1f}% over last 5 readings). {'Accelerating degradation likely.' if abs(trend) > 0.25 else 'Monitor trend.'}",
                    }
                )

    # Prediction context
    if predictions:
        latest_pred = predictions[-1] if predictions else {}
        prob = latest_pred.get("failure_prob", 0)
        if prob > 0.7:
            issues.append(
                {
                    "severity": "critical",
                    "sensor": "model",
                    "value": prob,
                    "message": f"ML model predicts HIGH failure risk ({prob * 100:.0f}%). Immediate action recommended.",
                }
            )
        elif prob > 0.4:
            issues.append(
                {
                    "severity": "warning",
                    "sensor": "model",
                    "value": prob,
                    "message": f"ML model predicts elevated failure risk ({prob * 100:.0f}%). Schedule inspection.",
                }
            )

    # Active alerts context
    alert_count = len(alerts) if alerts else 0

    # Build summary
    critical = [i for i in issues if i["severity"] == "critical"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    if critical:
        summary_parts.append(
            f"🚨 {len(critical)} critical issue{'s' if len(critical) > 1 else ''} detected"
        )
    if warnings:
        summary_parts.append(
            f"⚠️ {len(warnings)} warning{'s' if len(warnings) > 1 else ''}"
        )
    if not issues:
        summary_parts.append("✅ All sensors within normal ranges")
    if alert_count:
        summary_parts.append(
            f"🔔 {alert_count} active alert{'s' if alert_count > 1 else ''}"
        )

    # Recommendations
    recommendations = []
    for issue in issues:
        if issue["severity"] == "critical":
            recommendations.append(
                {
                    "priority": "immediate",
                    "action": issue["message"],
                    "sensor": issue["sensor"],
                }
            )
        elif issue["severity"] == "warning":
            recommendations.append(
                {
                    "priority": "schedule",
                    "action": issue["message"],
                    "sensor": issue["sensor"],
                }
            )

    return {
        "vehicle": vehicle_info.get("vehicle_id_display", "Unknown"),
        "summary": ". ".join(summary_parts) or "No data",
        "health_score": vehicle_info.get("health_score"),
        "issues": issues,
        "recommendations": recommendations[:8],
        "total_issues": len(issues),
        "critical_count": len(critical),
    }


def generate_report(
    vehicle_info: dict, readings: list[dict], predictions: list[dict] | None = None
) -> str:
    """Generate a plain-text maintenance report."""
    analysis = analyze_vehicle_health(vehicle_info, readings, predictions)
    lines = [
        f"Vehicle Health Report: {analysis['vehicle']}",
        "=" * 40,
        "",
        f"Summary: {analysis['summary']}",
        "",
    ]
    if analysis["issues"]:
        lines.append("Issues Found:")
        for i in analysis["issues"]:
            lines.append(f"  [{i['severity'].upper()}] {i['message']}")
    if analysis["recommendations"]:
        lines.append("", "Recommendations:")
        for r in analysis["recommendations"]:
            lines.append(f"  [{r['priority']}] {r['action']}")
    return "\n".join(lines)
