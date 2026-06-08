"""
Smart Traffic Monitoring System (STMS) — Cameras Router

Endpoint CRUD untuk manajemen kamera monitoring.
- GET / → public (JWT required)
- GET /internal/config → internal only (X-Internal-Key header required, no JWT)
- POST/PATCH → admin role (JWT required)

FIXED: Added /internal/config endpoint for CV module authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .. import models, schemas, config
from ..dependencies import get_db, get_any_authenticated_user, require_role

router = APIRouter(prefix="/api/v1/cameras", tags=["Cameras"])


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL ENDPOINT: GET /api/v1/cameras/internal/config
# For CV module to fetch camera configs WITHOUT JWT (uses X-Internal-Key instead)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/internal/config", response_model=list[schemas.CameraResponse])
def get_cameras_config_internal(
    db: Session = Depends(get_db),
    x_internal_key: str = Header(None)
):
    """
    Internal endpoint for CV module to fetch camera configurations.
    
    Auth: Requires X-Internal-Key header (not JWT token).
    This bypasses JWT requirement so CV can fetch configs on startup.
    
    Returns: List of all camera objects with their virtual line coordinates.
    """
    # Verify internal API key
    if x_internal_key != config.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Internal-Key header"
        )
    
    return db.query(models.Camera).all()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/cameras — Ambil semua kamera (semua role yang sudah login)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=list[schemas.CameraResponse])
def get_all_cameras(
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(get_any_authenticated_user)
):
    """Kembalikan daftar semua kamera terdaftar."""
    return db.query(models.Camera).all()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/cameras — Tambah atau update kamera (role: admin)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=schemas.CameraResponse)
def create_camera(
    camera: schemas.CameraCreate,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(require_role("admin"))
):
    """
    Tambah kamera baru. Jika camera_id sudah ada → update data yang ada.
    Hanya role admin yang boleh menambah/mengubah kamera.
    """
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera.camera_id
    ).first()

    # Jika ID sudah ada, update saja datanya
    if db_camera:
        for key, value in camera.model_dump().items():
            setattr(db_camera, key, value)
        db.commit()
        db.refresh(db_camera)
        return db_camera

    new_camera = models.Camera(**camera.model_dump())
    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)
    return new_camera


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/cameras/{camera_id}/archive — Toggle aktif/arsip (role: admin)
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{camera_id}/archive")
def archive_camera(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(require_role("admin"))
):
    """Toggle status kamera antara 'active' dan 'archived'. Hanya role admin."""
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()
    if not db_camera:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")

    db_camera.status = "archived" if db_camera.status == "active" else "active"
    db.commit()
    return {
        "status": "success",
        "message": f"Status kamera {camera_id} diubah menjadi {db_camera.status}"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /api/v1/cameras/{camera_id}/line — Update posisi garis virtual (role: admin)
# ═══════════════════════════════════════════════════════════════════════════════

class VirtualLineUpdate(BaseModel):
    line_x1: int
    line_y1: int
    line_x2: int
    line_y2: int


@router.patch("/{camera_id}/line")
def update_camera_line(
    camera_id: str,
    line_data: VirtualLineUpdate,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(require_role("admin"))
):
    """Update posisi garis virtual fleksibel (2 titik) untuk kamera. Hanya role admin."""
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()
   
    if not db_camera:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")

    # Update keempat koordinat
    db_camera.line_x1 = line_data.line_x1
    db_camera.line_y1 = line_data.line_y1
    db_camera.line_x2 = line_data.line_x2
    db_camera.line_y2 = line_data.line_y2
   
    db.commit()
    return {"message": f"Garis virtual {camera_id} berhasil diperbarui."}