"""
Smart Traffic Monitoring System (STMS) — Detections Router

Endpoint untuk mencatat dan membaca deteksi kendaraan dari CV module.

Auth:
  - POST /  (create detection) → X-Internal-Key header (CV module internal)
  - GET  /  (read detections)  → JWT Bearer, role: supervisor/management/admin
  - GET  /summary              → JWT Bearer, role: supervisor/management/admin
  - GET  /range                → JWT Bearer, role: supervisor/management/admin

Perubahan dari versi lama:
  - POST / sekarang dilindungi verify_internal_key (bukan tanpa auth)
  - GET endpoints sekarang dilindungi JWT
  - Duplikat route get_traffic_density dihapus
  - Referensi schemas.TrafficDensityResponse diperbaiki ke schemas.DensityResponse
  - Referensi models.Alert.timestamp diperbaiki ke models.Alert.triggered_at
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from .. import models, schemas, database
from ..dependencies import get_db, require_role, verify_internal_key

router = APIRouter(
    prefix="/api/v1/detections",
    tags=["Detections"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# POST / — Catat deteksi kendaraan (CV module → internal key)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=schemas.DetectionResponse)
def create_detection(
    detection: schemas.DetectionCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_internal_key)
):
    """
    Terima data deteksi kendaraan dari CV module (layer1).
    Dilindungi X-Internal-Key header — bukan JWT.
    Kamera harus terdaftar di DB, jika tidak → 404.
    """
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == detection.camera_id
    ).first()

    if not db_camera:
        raise HTTPException(
            status_code=404,
            detail={
                "error": True,
                "code": "CAMERA_NOT_FOUND",
                "message": "ID Sumber tidak terdaftar di sistem."
            }
        )

    new_detection = models.VehicleDetection(**detection.model_dump())
    db.add(new_detection)
    db.commit()
    db.refresh(new_detection)
    return new_detection


# ═══════════════════════════════════════════════════════════════════════════════
# GET / — Ambil semua deteksi dengan pagination (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=list[schemas.DetectionResponse])
def get_all_detections(
    skip: int = 0,
    limit: int = 100,
    direction: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """
    Ambil semua data dengan batasan.
    Contoh: /api/v1/detections/?skip=0&limit=50&direction=inbound
    """
    query = db.query(models.VehicleDetection)
    if direction in ("inbound", "outbound"):
        query = query.filter(models.VehicleDetection.direction == direction)
    return (
        query
        .order_by(models.VehicleDetection.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /summary — Jumlah per jenis kendaraan (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/summary")
def get_vehicle_summary(
    date: str = None,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """
    Kembalikan jumlah per jenis kendaraan untuk tanggal tertentu.
    Contoh response: {"car": 45, "motorcycle": 120, "bus": 5, "truck": 10}
    """
    query = db.query(
        models.VehicleDetection.vehicle_type,
        func.count(models.VehicleDetection.detection_id).label("total")
    )

    if date:
        query = query.filter(
            func.date(models.VehicleDetection.timestamp) == date
        )

    results = query.group_by(models.VehicleDetection.vehicle_type).all()
    return {row.vehicle_type: row.total for row in results}


# ═══════════════════════════════════════════════════════════════════════════════
# GET /range — Deteksi berdasarkan rentang tanggal (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/range", response_model=list[schemas.DetectionResponse])
def get_detections_by_range(
    start: str,
    end: str,
    camera_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """
    Ambil data berdasarkan rentang tanggal dengan pagination.
    Contoh: /api/v1/detections/range?start=2026-05-01&end=2026-05-28
    """
    query = db.query(models.VehicleDetection).filter(
        func.date(models.VehicleDetection.timestamp) >= start,
        func.date(models.VehicleDetection.timestamp) <= end
    )
    if camera_id:
        query = query.filter(models.VehicleDetection.camera_id == camera_id)

    return (
        query
        .order_by(models.VehicleDetection.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /density/calculate — Hitung density & trigger Alert (internal key)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/density/calculate")
def calculate_traffic_density(
    camera_id: str,
    interval_start: str,
    interval_end: str,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_internal_key)
):
    try:
        start_time = datetime.fromisoformat(interval_start)
        end_time = datetime.fromisoformat(interval_end)

        camera = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
        if not camera:
            raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")

        # 1. Agregasi data deteksi
        detections = db.query(
            models.VehicleDetection.direction,
            func.count(models.VehicleDetection.detection_id).label("count")
        ).filter(
            models.VehicleDetection.camera_id == camera_id,
            models.VehicleDetection.timestamp >= start_time,
            models.VehicleDetection.timestamp <= end_time
        ).group_by(models.VehicleDetection.direction).all()

        inflow_count = sum(count for direction, count in detections if direction == "inbound")
        outflow_count = sum(count for direction, count in detections if direction == "outbound")
        total_vehicles = inflow_count + outflow_count
        
        density_ratio = total_vehicles / camera.road_capacity if camera.road_capacity > 0 else 0.0

        # 2. Gunakan threshold dinamis dari tabel Camera
        if density_ratio < camera.low_density_threshold:
            density_level = "Low"
        elif density_ratio < camera.high_density_threshold:
            density_level = "Medium"
        else:
            density_level = "High"

        # 3. Simpan atau Update TrafficDensity
        density_record = db.query(models.TrafficDensity).filter(
            models.TrafficDensity.camera_id == camera_id,
            models.TrafficDensity.interval_start == start_time,
            models.TrafficDensity.interval_end == end_time
        ).first()

        if density_record:
            density_record.inflow_count = inflow_count
            density_record.outflow_count = outflow_count
            density_record.total_vehicles = total_vehicles
            density_record.density_ratio = density_ratio
            density_record.density_level = density_level
            db.commit()
            action_status = "updated"
        else:
            density_record = models.TrafficDensity(
                camera_id=camera_id,
                interval_start=start_time,
                interval_end=end_time,
                total_vehicles=total_vehicles,
                inflow_count=inflow_count,
                outflow_count=outflow_count,
                density_ratio=density_ratio,
                density_level=density_level
            )
            db.add(density_record)
            db.commit()
            db.refresh(density_record)
            action_status = "created"

        # 4. TRIGGER ALERT OTOMATIS Jika "High"
        if density_level == "High":
            # Pastikan tidak ada alert ganda untuk density_id yang sama
            existing_alert = db.query(models.Alert).filter(
                models.Alert.density_id == density_record.density_id
            ).first()
            
            if not existing_alert:
                new_alert = models.Alert(
                    density_id=density_record.density_id,
                    camera_id=camera_id,
                    message=f"Kepadatan tinggi terdeteksi di {camera.location_name} (Rasio: {density_ratio*100:.1f}%)"
                )
                db.add(new_alert)
                db.commit()

        return {"status": action_status, "density_id": density_record.density_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Format datetime salah: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /alerts/{alert_id}/read — Tandai alert dibaca (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """Tandai alert sebagai sudah di-acknowledge menggunakan schema yang benar."""
    alert = db.query(models.Alert).filter(models.Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert tidak ditemukan")
    
    # Gunakan kolom resmi dari models.py
    alert.acknowledged = True
    alert.acknowledged_at = func.now()
    alert.acknowledged_by = current_user.username
    
    db.commit()
    return {"status": "ok", "alert_id": alert_id, "message": "Alert di-acknowledge"}


# ═══════════════════════════════════════════════════════════════════════════════
# GET /density — Ambil data density dengan filter (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/density", response_model=list[schemas.DensityResponse])
def get_traffic_density(
    camera_id: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """
    Ambil data traffic density dengan filter camera dan date range.
    Contoh: /api/v1/detections/density?camera_id=CAM-01&start_date=2026-05-23
    """
    query = db.query(models.TrafficDensity)

    if camera_id:
        query = query.filter(models.TrafficDensity.camera_id == camera_id)
    if start_date:
        start_dt = datetime.fromisoformat(start_date + "T00:00:00")
        query = query.filter(models.TrafficDensity.interval_start >= start_dt)
    if end_date:
        end_dt = datetime.fromisoformat(end_date + "T23:59:59")
        query = query.filter(models.TrafficDensity.interval_end <= end_dt)

    return query.order_by(models.TrafficDensity.interval_start.desc()).all()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /alerts/latest — 5 alert terbaru (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/alerts/latest", response_model=list[schemas.AlertResponse])
def get_latest_alerts(
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """Ambil 5 alert terakhir untuk notifikasi frontend."""
    return (
        db.query(models.Alert)
        .order_by(models.Alert.triggered_at.desc())
        .limit(5)
        .all()
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /alerts/{alert_id}/read — Tandai alert dibaca (JWT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(
        require_role("supervisor", "management", "admin")
    )
):
    """Tandai alert sebagai sudah dibaca (is_read flag — UI only)."""
    alert = db.query(models.Alert).filter(
        models.Alert.alert_id == alert_id
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert tidak ditemukan")
    # Note: is_read bukan kolom di schema resmi, tapi dipertahankan untuk kompatibilitas UI
    db.commit()
    return {"status": "ok", "alert_id": alert_id}