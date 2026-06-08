"""
Smart Traffic Monitoring System (STMS) — Detections Router

Endpoint untuk mencatat dan membaca deteksi kendaraan dari CV module.
Perbaikan Audit:
 - POST / diubah auth-nya untuk menerima JWT (karena AI kita menggunakan Login JWT).
 - Menghapus rute usang (alerts dan density) untuk memusatkan Single Source of Truth.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from .. import models, schemas, database
from ..dependencies import get_db, require_role, verify_internal_key, get_any_authenticated_user

router = APIRouter(
    prefix="/api/v1/detections",
    tags=["Detections"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# POST / — Catat deteksi kendaraan (DARI AI YOLOv8)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=schemas.DetectionResponse)
def create_detection(
    detection: schemas.DetectionCreate,
    db: Session = Depends(get_db),
    # FIX: Mengizinkan AI yang sudah login (bawa JWT) untuk mengirim data
    current_user: models.UserAccount = Depends(get_any_authenticated_user) 
):
    """
    Terima data deteksi kendaraan dari CV module (layer1).
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
    # (Di sini Scheduler bekerja otomatis merangkum data 5/15 menit)
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