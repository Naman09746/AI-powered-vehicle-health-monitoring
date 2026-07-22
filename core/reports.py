"""
PDF report generation using ReportLab.
Generates per-vehicle reports with vehicle details, health score, predictions,
recommendations, charts, and model summaries.
"""

import datetime
import io

import matplotlib

# Set non-interactive backend only if not already configured (e.g., by Streamlit)
if matplotlib.get_backend() == matplotlib.rcParams.get("backend", ""):
    matplotlib.use("Agg")
elif "agg" not in matplotlib.get_backend().lower():
    # Already configured with a non-Agg backend — warn but don't override
    import logging

    logging.getLogger("reports").warning(
        "Matplotlib already configured with '%s'; PDF may not work",
        matplotlib.get_backend(),
    )
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_pdf(
    vehicle_info: dict,
    health_data: dict,
    prediction: dict | None,
    recommendations: list[dict],
    sensor_data: dict | None = None,
    model_summary: dict | None = None,
) -> bytes:
    """
    Generate a PDF report for a vehicle.

    Args:
        vehicle_info: Dict with vehicle details.
        health_data: Dict from core.health_score.calculate_health_score().
        prediction: Dict from ml.ml_models.predict() or None.
        recommendations: List of recommendation dicts.
        sensor_data: Optional dict of latest sensor readings.
        model_summary: Optional dict with model performance metrics.

    Returns:
        PDF file as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(
        ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#16213e"),
            spaceBefore=15,
            spaceAfter=8,
            borderWidth=1,
            borderColor=colors.HexColor("#e0e0e0"),
            borderPadding=5,
        )
    )
    styles.add(
        ParagraphStyle(
            "BodyTextCustom",
            parent=styles["BodyText"],
            fontSize=10,
            leading=14,
        )
    )
    styles.add(
        ParagraphStyle(
            "CenterText",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontSize=10,
        )
    )

    elements = []

    # ── Title ──
    elements.append(Paragraph("Vehicle Health Report", styles["ReportTitle"]))
    elements.append(
        Paragraph(
            f"Generated on {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            styles["CenterText"],
        )
    )
    elements.append(Spacer(1, 15))
    elements.append(
        HRFlowable(width="100%", color=colors.HexColor("#1a1a2e"), thickness=2)
    )
    elements.append(Spacer(1, 15))

    # ── Vehicle Details ──
    elements.append(Paragraph("Vehicle Details", styles["SectionTitle"]))
    vehicle_table_data = [
        ["Vehicle ID", str(vehicle_info.get("vehicle_id_display", "N/A"))],
        ["Model", str(vehicle_info.get("model", "N/A"))],
        ["Year", str(vehicle_info.get("manufacturing_year", "N/A"))],
        ["Engine Type", str(vehicle_info.get("engine_type", "N/A"))],
        ["Mileage", f"{vehicle_info.get('mileage', 'N/A')} km"],
        ["Last Service", str(vehicle_info.get("last_service_date", "N/A"))],
    ]
    t = Table(vehicle_table_data, colWidths=[150, 350])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f5")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(t)
    elements.append(Spacer(1, 15))

    # ── Health Score ──
    elements.append(Paragraph("Health Score", styles["SectionTitle"]))
    score = health_data.get("score", 0)
    band = health_data.get("band_name", "Unknown")
    band_color = health_data.get("band_color", "#999999")

    # Health score gauge as a chart image
    gauge_img = _create_gauge_image(score, band, band_color)
    elements.append(Image(gauge_img, width=3 * inch, height=2 * inch))
    elements.append(
        Paragraph(
            f"<b>Score: {score}/100</b> - Status: <font color='{band_color}'><b>{band}</b></font>",
            styles["CenterText"],
        )
    )
    if health_data.get("breakdown"):
        elements.append(
            Paragraph(
                f"<i>Formula: {health_data['breakdown']['formula']}</i>",
                styles["CenterText"],
            )
        )
    elements.append(Spacer(1, 15))

    # ── Prediction Result ──
    if prediction:
        elements.append(Paragraph("Failure Prediction", styles["SectionTitle"]))
        pred_table = [
            ["Prediction", prediction.get("prediction_class", "N/A")],
            ["Failure Probability", f"{prediction.get('failure_prob', 0):.1%}"],
            ["Model Confidence", f"{prediction.get('confidence', 0):.1%}"],
        ]
        t = Table(pred_table, colWidths=[150, 350])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f5")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 10))

        # Top contributing features
        feature_imps = prediction.get("feature_importances", [])
        if feature_imps:
            elements.append(
                Paragraph("Top Contributing Factors:", styles["BodyTextCustom"])
            )
            for f in feature_imps[:5]:
                elements.append(
                    Paragraph(
                        f"• {f['feature'].replace('_', ' ').title()}: {f['contribution_pct']:.1f}% contribution",
                        styles["BodyTextCustom"],
                    )
                )
        elements.append(Spacer(1, 15))

    # ── Recommendations ──
    if recommendations:
        elements.append(
            Paragraph("Maintenance Recommendations", styles["SectionTitle"])
        )
        rec_data = [["Priority", "Action", "Sensor", "Recommended By"]]
        for rec in recommendations:
            rec_data.append(
                [
                    rec.get("priority", "N/A"),
                    rec.get("action", "N/A"),
                    rec.get("sensor_label", "N/A"),
                    rec.get("recommended_date", "N/A"),
                ]
            )
        t = Table(rec_data, colWidths=[70, 200, 100, 100])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8f8ff")],
                    ),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 15))

    # ── Model Summary ──
    if model_summary:
        elements.append(Paragraph("Model Performance Summary", styles["SectionTitle"]))
        elements.append(
            Paragraph(
                f"Best Model: <b>{model_summary.get('best_model', 'N/A')}</b>",
                styles["BodyTextCustom"],
            )
        )
        if model_summary.get("results"):
            model_data = [["Model", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"]]
            for r in model_summary["results"]:
                if r.get("metrics"):
                    m = r["metrics"]
                    model_data.append(
                        [
                            r["name"],
                            f"{m.get('accuracy', 0):.4f}",
                            f"{m.get('precision', 0):.4f}",
                            f"{m.get('recall', 0):.4f}",
                            f"{m.get('f1', 0):.4f}",
                            f"{m.get('roc_auc', 0):.4f}" if m.get("roc_auc") else "N/A",
                        ]
                    )
            t = Table(model_data, colWidths=[100, 75, 75, 75, 75, 75])
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f8f8ff")],
                        ),
                    ]
                )
            )
            elements.append(t)

    # ── Footer ──
    elements.append(Spacer(1, 30))
    elements.append(
        HRFlowable(width="100%", color=colors.HexColor("#cccccc"), thickness=1)
    )
    elements.append(
        Paragraph(
            "This report was automatically generated by the Vehicle Health Monitoring System. "
            "Predictions are based on ML models trained on sensor data and should be used as "
            "guidance alongside professional mechanical inspection.",
            ParagraphStyle(
                "Footer",
                parent=styles["BodyText"],
                fontSize=8,
                textColor=colors.HexColor("#999999"),
                alignment=TA_CENTER,
            ),
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _create_gauge_image(score: float, band: str, color: str) -> io.BytesIO:
    """Create a gauge chart as a PNG image for the PDF."""
    fig, ax = plt.subplots(figsize=(4, 2.5), subplot_kw={"projection": "polar"})

    # Gauge settings
    start_angle = np.pi
    end_angle = 0
    angle_range = start_angle - end_angle

    # Background arc segments (colored bands)
    band_configs = [
        (0, 60, "#FF4444"),  # Critical
        (60, 80, "#FFBB33"),  # Warning
        (80, 95, "#33B5E5"),  # Good
        (95, 100, "#00C851"),  # Excellent
    ]

    for band_min, band_max, band_color in band_configs:
        theta_start = start_angle - (band_min / 100) * angle_range
        theta_end = start_angle - (band_max / 100) * angle_range
        theta = np.linspace(theta_start, theta_end, 50)
        ax.fill_between(theta, 0.7, 1.0, color=band_color, alpha=0.3)

    # Needle
    needle_angle = start_angle - (score / 100) * angle_range
    ax.plot([needle_angle, needle_angle], [0, 0.85], color=color, linewidth=3)
    ax.plot(needle_angle, 0.85, "o", color=color, markersize=8)

    # Center
    ax.plot(0, 0, "o", color="#333", markersize=6)

    ax.set_ylim(0, 1.1)
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    ax.set_rticks([])
    ax.set_thetagrids([])
    ax.spines["polar"].set_visible(False)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    # Score text
    fig.text(
        0.5,
        0.15,
        f"{score:.0f}/100",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color=color,
    )
    fig.text(0.5, 0.05, band, ha="center", va="center", fontsize=12, color=color)

    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        dpi=150,
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    buf.seek(0)
    return buf
