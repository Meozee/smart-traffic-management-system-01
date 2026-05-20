from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date

from .. import models, schemas, database

router = APIRouter(
    prefix="/api/v1/detections",
    tags=["Detections"]
)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# CREATE DETECTION
# =========================
@router.post("/", response_model=schemas.DetectionResponse)
def create_detection(
    detection: schemas.DetectionCreate,
    db: Session = Depends(get_db)
):
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == detection.camera_id
    ).first()

    if not db_camera:
        raise HTTPException(
            status_code=404,
            detail="ID Sumber tidak terdaftar di sistem"
        )

    new_detection = models.VehicleDetection(**detection.model_dump())
    db.add(new_detection)
    db.commit()
    db.refresh(new_detection)
    return new_detection


# =========================
# GET ALL DETECTIONS (WITH PAGINATION)
# =========================
@router.get("/", response_model=list[schemas.DetectionResponse])
def get_all_detections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Mengambil semua data dengan batasan.
    Contoh: /api/v1/detections/?skip=0&limit=50 (Ambil 50 data pertama)
    """
    return db.query(models.VehicleDetection).offset(skip).limit(limit).all()


# =========================
# GET VEHICLE TYPE SUMMARY (untuk grafik klasifikasi)
# =========================
@router.get("/summary")
def get_vehicle_summary(
    date: str = None,
    db: Session = Depends(get_db)
):
    """
    Mengembalikan jumlah per jenis kendaraan untuk tanggal tertentu.
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


# =========================
# GET DETECTIONS BY DATE RANGE (WITH PAGINATION)
# =========================
@router.get("/range", response_model=list[schemas.DetectionResponse])
def get_detections_by_range(
    start: str,
    end: str,
    camera_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Mengambil data berdasarkan rentang tanggal dengan Pagination.
    Dilarutkan dari yang terbaru (descending).
    """
    query = db.query(models.VehicleDetection).filter(
        func.date(models.VehicleDetection.timestamp) >= start,
        func.date(models.VehicleDetection.timestamp) <= end
    )
    if camera_id:
        query = query.filter(models.VehicleDetection.camera_id == camera_id)

    # Tambahan .offset() dan .limit() di akhir query
    return query.order_by(models.VehicleDetection.timestamp.desc()).offset(skip).limit(limit).all()