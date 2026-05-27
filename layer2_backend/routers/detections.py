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
def get_all_detections(
    skip: int = 0,
    limit: int = 100,
    direction: str | None = None,
    db: Session = Depends(get_db)
):
    """
    Mengambil semua data dengan batasan.
    Contoh: /api/v1/detections/?skip=0&limit=50&direction=inbound
    """
    query = db.query(models.VehicleDetection)
    if direction in ("inbound", "outbound"):
        query = query.filter(models.VehicleDetection.direction == direction)
    return query.order_by(models.VehicleDetection.timestamp.desc()).offset(skip).limit(limit).all()


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


# =========================
# CALCULATE TRAFFIC DENSITY (POST endpoint)
# =========================
@router.post("/density/calculate")
def calculate_traffic_density(
    camera_id: str,
    interval_start: str,  # Format: "2026-05-23T10:00:00"
    interval_end: str,    # Format: "2026-05-23T11:00:00"
    db: Session = Depends(get_db)
):
    """
    Hitung traffic density untuk interval waktu tertentu.
    Agregasi inbound, outbound, dan hitung density ratio.
    Simpan ke tabel traffic_density.
    """
    try:
        # Parse datetime strings
        start_time = datetime.fromisoformat(interval_start)
        end_time = datetime.fromisoformat(interval_end)
        
        # Validasi kamera ada
        camera = db.query(models.Camera).filter(
            models.Camera.camera_id == camera_id
        ).first()
        
        if not camera:
            raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")
        
        # Query detections dalam interval, agregasi per direction
        detections = db.query(
            models.VehicleDetection.direction,
            func.count(models.VehicleDetection.detection_id).label("count")
        ).filter(
            models.VehicleDetection.camera_id == camera_id,
            models.VehicleDetection.timestamp >= start_time,
            models.VehicleDetection.timestamp <= end_time
        ).group_by(models.VehicleDetection.direction).all()
        
        # Hitung inbound dan outbound
        inflow_count = 0
        outflow_count = 0
        
        for direction, count in detections:
            if direction == "inbound":
                inflow_count = count
            elif direction == "outbound":
                outflow_count = count
        
        total_vehicles = inflow_count + outflow_count
        
        # Hitung density ratio
        density_ratio = total_vehicles / camera.road_capacity if camera.road_capacity > 0 else 0
        
        # Tentukan density level
        if density_ratio < 0.3:
            density_level = "Low"
        elif density_ratio < 0.7:
            density_level = "Medium"
        else:
            density_level = "High"
        
        # Cek apakah sudah ada record untuk interval ini
        existing_density = db.query(models.TrafficDensity).filter(
            models.TrafficDensity.camera_id == camera_id,
            models.TrafficDensity.interval_start == start_time,
            models.TrafficDensity.interval_end == end_time
        ).first()
        
        if existing_density:
            # Update existing record
            existing_density.inflow_count = inflow_count
            existing_density.outflow_count = outflow_count
            existing_density.total_vehicles = total_vehicles
            existing_density.density_ratio = density_ratio
            existing_density.density_level = density_level
            db.commit()
            return {"status": "updated", "density_id": existing_density.density_id}
        else:
            # Create new record
            new_density = models.TrafficDensity(
                camera_id=camera_id,
                interval_start=start_time,
                interval_end=end_time,
                total_vehicles=total_vehicles,
                inflow_count=inflow_count,
                outflow_count=outflow_count,
                density_ratio=density_ratio,
                density_level=density_level
            )
            db.add(new_density)
            # Jika density tinggi, buat alert juga
            try:
                if density_level.upper() == "HIGH":
                    alert_msg = f"Peringatan: Kepadatan tinggi ({density_ratio*100:.1f}%) terdeteksi di {camera.location_name}."
                    new_alert = models.Alert(
                        camera_id=camera_id,
                        message=alert_msg
                    )
                    db.add(new_alert)
            except Exception:
                # Jangan biarkan alert gagal menghentikan proses utama
                pass
            db.commit()
            db.refresh(new_density)
            return {"status": "created", "density_id": new_density.density_id}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Format datetime salah: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# =========================
# GET TRAFFIC DENSITY (GET endpoint)
# =========================
@router.get("/density", response_model=list[schemas.TrafficDensityResponse])
def get_traffic_density(
    camera_id: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Ambil data traffic density dengan filter camera dan date range.
    Contoh: /api/v1/detections/density?camera_id=CAM-01&start_date=2026-05-23&end_date=2026-05-23
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

@router.get("/density", response_model=list[schemas.TrafficDensityResponse])
def get_traffic_density(
    camera_id: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
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


# =========================
# GET LATEST ALERTS
# =========================
@router.get("/alerts/latest", response_model=list[schemas.AlertResponse])
def get_latest_alerts(db: Session = Depends(get_db)):
    """
    Mengambil 5 alert terakhir untuk ditampilkan di notifikasi frontend.
    """
    return db.query(models.Alert).order_by(models.Alert.timestamp.desc()).limit(5).all()


# MARK ALERT AS READ
@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(models.Alert).filter(models.Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert tidak ditemukan")
    alert.is_read = True
    db.commit()
    return {"status": "ok", "alert_id": alert_id}