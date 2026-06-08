"""
Smart Traffic Monitoring System (STMS) — Alerts Router

Endpoints untuk membaca, acknowledge, dan membuat alert traffic.

PENTING — urutan route:
  /internal  →  didefinisikan LEBIH DULU daripada /{alert_id}/acknowledge
  agar FastAPI tidak salah parse string "internal" sebagai integer alert_id.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel

from .. import models, schemas
from ..dependencies import get_db, require_role, verify_internal_key

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


# ── Schema inline untuk POST /internal ─────────────────────────────────────────
class AlertCreate(BaseModel):
    """Request body untuk endpoint internal (CV module → backend)."""
    density_id: int
    camera_id: str
    triggered_at: Optional[datetime] = None
    density_level: str = "High"
    alert_type: str = "High Density"
    severity: str = "High"
    message: str
    acknowledged: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/alerts/internal   ← HARUS didefinisikan SEBELUM /{alert_id}/...
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/internal",
    response_model=schemas.AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Buat alert baru dari CV module",
    description=(
        "Endpoint internal untuk CV module membuat alert. "
        "Dilindungi X-Internal-Key header, bukan JWT. "
        "Jika density_id sudah punya alert → return existing alert (idempotent)."
    )
)
def create_internal_alert(
    alert_data: AlertCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_internal_key)
):
    """
    Logic:
    1. Cek apakah density_id sudah punya alert (UNIQUE constraint 1:1)
    2. Jika sudah ada → return existing dengan status 200
    3. Jika belum → INSERT baru, return dengan status 201
    """
    # Cek existing alert untuk density_id ini
    existing = db.query(models.Alert).filter(
        models.Alert.density_id == alert_data.density_id
    ).first()

    if existing:
        # Idempotent: kembalikan yang sudah ada, bukan error
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=schemas.AlertResponse.model_validate(existing).model_dump(mode="json")
        )

    # Tentukan triggered_at (default: sekarang UTC)
    triggered_at = alert_data.triggered_at or datetime.now(timezone.utc)

    new_alert = models.Alert(
        density_id=alert_data.density_id,
        camera_id=alert_data.camera_id,
        triggered_at=triggered_at,
        density_level=alert_data.density_level,
        alert_type=alert_data.alert_type,
        severity=alert_data.severity,
        message=alert_data.message,
        acknowledged=alert_data.acknowledged
    )

    try:
        db.add(new_alert)
        db.commit()
        db.refresh(new_alert)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "code": "DB_ERROR",
                "message": f"Gagal menyimpan alert: {str(e)}"
            }
        )

    return new_alert


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/alerts
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=List[schemas.AlertResponse],
    summary="Ambil daftar alert",
    description=(
        "Mengembalikan daftar alert diurutkan triggered_at DESC. "
        "status='active' → hanya yang belum di-acknowledge. "
        "status='all' → semua alert."
    )
)
def get_alerts(
    alert_status: str = Query(
        "active",
        alias="status",
        description="Filter status: 'active' (belum acknowledge) atau 'all'"
    ),
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    query = db.query(models.Alert)

    if alert_status == "active":
        query = query.filter(models.Alert.acknowledged == False)  # noqa: E712
    # "all" → tidak ada filter tambahan

    results = query.order_by(models.Alert.triggered_at.desc()).all()
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/alerts/{alert_id}/acknowledge
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{alert_id}/acknowledge",
    response_model=schemas.AlertResponse,
    summary="Acknowledge alert",
    description=(
        "Tandai alert sebagai sudah ditangani. "
        "Username diambil otomatis dari JWT token. "
        "Raise 400 jika alert sudah pernah di-acknowledge sebelumnya."
    )
)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(require_role("supervisor", "admin"))
):
    # 1. Cari alert berdasarkan ID
    alert = db.query(models.Alert).filter(
        models.Alert.alert_id == alert_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": True,
                "code": "ALERT_NOT_FOUND",
                "message": f"Alert dengan ID {alert_id} tidak ditemukan."
            }
        )

    # 2. Cek apakah sudah di-acknowledge
    if alert.acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": True,
                "code": "ALREADY_ACKNOWLEDGED",
                "message": "Alert sudah pernah di-acknowledge sebelumnya."
            }
        )

    # 3. Update acknowledged fields
    alert.acknowledged = True
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = current_user.username

    db.commit()
    db.refresh(alert)

    return alert
