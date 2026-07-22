"""
Reports router — generate and download PDF vehicle health reports.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import core.db as database
from api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{vehicle_id}/pdf")
async def generate_pdf_report(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Generate a PDF report for a vehicle."""
    vehicle = database.get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    try:
        from core.reports import generate_vehicle_report

        pdf_bytes = generate_vehicle_report(vehicle_id, user["id"])
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report_{vehicle_id}.pdf"',
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {exc}",
        )
