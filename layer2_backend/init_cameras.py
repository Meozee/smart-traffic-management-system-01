"""
Script untuk inisialisasi data default (kamera) saat backend startup
"""
from sqlalchemy.orm import Session
from . import models, database

def init_default_cameras():
    """Tambahkan kamera default saat database dibuat"""
    db = database.SessionLocal()
    
    try:
        # Cek apakah CAM-01 sudah ada
        existing = db.query(models.Camera).filter(
            models.Camera.camera_id == "CAM-01"
        ).first()
        
        if not existing:
            default_camera = models.Camera(
                camera_id="CAM-01",
                location_name="Central Aceh - Main Road",
                segment_id="SEG-01",
                road_capacity=100,
                status="active",
                stream_url="/app/videos/traffic.mp4",  # Path inside Docker container
                virtual_line_y=300
            )
            db.add(default_camera)
            db.commit()
            print("✅ Default kamera (CAM-01) berhasil ditambahkan ke database")
        else:
            print("ℹ️  Kamera CAM-01 sudah ada di database")
            
    except Exception as e:
        print(f"❌ Error saat inisialisasi kamera: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_default_cameras()
