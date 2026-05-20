from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(prefix="/api/v1/cameras", tags=["Cameras"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# POST: Tambah Kamera Baru (Atau Update URL jika ID sudah ada)
@router.post("/", response_model=schemas.CameraResponse)
def create_camera(camera: schemas.CameraCreate, db: Session = Depends(get_db)):
    db_camera = db.query(models.Camera).filter(models.Camera.camera_id == camera.camera_id).first()
    
    # PRO TIP: Jika ID sudah ada, kita update saja datanya
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

# GET: Ambil Semua Daftar Kamera
@router.get("/", response_model=list[schemas.CameraResponse])
def get_all_cameras(db: Session = Depends(get_db)):
    return db.query(models.Camera).all()

# PATCH: Fitur Arsitektur Pintar - Archive/Unarchive (Pengganti Delete)
@router.patch("/{camera_id}/archive")
def archive_camera(camera_id: str, db: Session = Depends(get_db)):
    db_camera = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
    if not db_camera:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")
    
    # Toggle status: Jika aktif jadi arsip, jika arsip jadi aktif kembali
    if db_camera.status == "active":
        db_camera.status = "archived"
    else:
        db_camera.status = "active"
        
    db.commit()
    return {"status": "success", "message": f"Status kamera {camera_id} diubah menjadi {db_camera.status}"}


# Tambahkan di routers/cameras.py
@router.patch("/{camera_id}/line")
def update_camera_line(camera_id: str, y_position: int, db: Session = Depends(get_db)):
    db_camera = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
    if not db_camera:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")
    
    db_camera.virtual_line_y = y_position
    db.commit()
    return {"message": f"Garis virtual {camera_id} diupdate ke {y_position}px"}