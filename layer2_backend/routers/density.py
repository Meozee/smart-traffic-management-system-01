"""
Smart Traffic Monitoring System (STMS) — Density Router

Endpoints untuk membaca data traffic density (real-time & history).
Perbaikan Audit:
 - Menambahkan 'supervisor' pada role akses /history agar grafik dashboard tidak crash 
   saat diakses oleh petugas lapangan.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import Optional, List
from collections import defaultdict
import statistics

from .. import models, schemas
from ..dependencies import get_db, require_role

router = APIRouter(prefix="/api/v1/density", tags=["Density"])

# ─── Nama hari dalam Bahasa Indonesia (weekday() → 0=Senin … 6=Minggu) ─────────
HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/density/realtime
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/realtime",
    response_model=List[schemas.DensityResponse],
    summary="Ambil density terbaru per kamera (real-time)"
)
def get_realtime_density(
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(require_role("supervisor", "management", "admin"))
):
    subq = (
        db.query(
            models.TrafficDensity.camera_id,
            func.max(models.TrafficDensity.interval_end).label("max_end")
        )
        .group_by(models.TrafficDensity.camera_id)
        .subquery()
    )

    results = (
        db.query(models.TrafficDensity)
        .join(
            subq,
            (models.TrafficDensity.camera_id == subq.c.camera_id) &
            (models.TrafficDensity.interval_end == subq.c.max_end)
        )
        .all()
    )

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/density/history
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/history",
    summary="Ambil history density dalam rentang tanggal"
)
def get_density_history(
    start_date: datetime = Query(..., description="Batas awal rentang (ISO 8601, UTC)"),
    end_date: datetime = Query(..., description="Batas akhir rentang (ISO 8601, UTC)"),
    camera_id: Optional[str] = Query(None, description="Filter per camera_id (opsional)"),
    db: Session = Depends(get_db),
    # FIX: Menambahkan 'supervisor' agar grafik bisa dimuat oleh staf lapangan
    current_user: models.UserAccount = Depends(require_role("supervisor", "management", "admin"))
):
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail={
                "error": True,
                "code": "INVALID_DATE_RANGE",
                "message": "start_date tidak boleh lebih besar dari end_date."
            }
        )

    query = db.query(models.TrafficDensity).filter(
        models.TrafficDensity.interval_start >= start_date,
        models.TrafficDensity.interval_end <= end_date
    )

    if camera_id:
        query = query.filter(models.TrafficDensity.camera_id == camera_id)

    records = query.order_by(models.TrafficDensity.interval_start.asc()).all()

    if not records:
        return {"data": [], "summary": None}

    # 1. Total kendaraan
    total_vehicles = sum(r.total_vehicles for r in records)

    # 2. Rata-rata density ratio (skip None)
    ratios = [r.density_ratio for r in records if r.density_ratio is not None]
    average_density_ratio = round(statistics.mean(ratios), 4) if ratios else 0.0

    # 3. Peak hour
    hour_groups: dict = defaultdict(list)
    for r in records:
        if r.density_ratio is not None:
            hour_groups[r.interval_start.hour].append(r.density_ratio)

    if hour_groups:
        peak_h = max(hour_groups, key=lambda h: statistics.mean(hour_groups[h]))
        peak_hour = f"{peak_h:02d}:00 - {(peak_h + 1) % 24:02d}:00"
    else:
        peak_hour = None

    # 4. Peak day
    day_groups: dict = defaultdict(int)
    for r in records:
        day_key = r.interval_start.date()
        day_groups[day_key] += r.total_vehicles

    if day_groups:
        peak_date = max(day_groups, key=lambda d: day_groups[d])
        peak_day = f"{HARI_ID[peak_date.weekday()]}, {peak_date.strftime('%Y-%m-%d')}"
    else:
        peak_day = None

    # 5. Density distribution
    total_recs = len(records)
    dist_counts: dict = {"Low": 0, "Medium": 0, "High": 0}
    for r in records:
        level = r.density_level
        if level in dist_counts:
            dist_counts[level] += 1
    density_distribution = {
        k: round(v / total_recs * 100, 1)
        for k, v in dist_counts.items()
    }

    serialized_data = [schemas.DensityResponse.model_validate(r) for r in records]

    summary = schemas.ReportSummary(
        total_vehicles=total_vehicles,
        average_density_ratio=average_density_ratio,
        peak_hour=peak_hour,
        peak_day=peak_day,
        density_distribution=density_distribution
    )

    return {
        "data": serialized_data,
        "summary": summary
    }