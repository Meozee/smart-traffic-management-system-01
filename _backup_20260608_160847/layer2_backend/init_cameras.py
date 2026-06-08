"""
Script untuk inisialisasi data default (kamera) saat backend startup.

FIX:
- Menghapus virtual_line_y yang sudah usang.
- Menggantinya dengan 4 titik koordinat garis fleksibel (line_x1, line_y1, line_x2, line_y2).
- Menambahkan parameter ambang batas AI (threshold).
"""
from sqlalchemy.orm import Session
from . import models, database

def init_default_cameras():
    """Tambahkan kamera default saat database dibuat."""
    db = database.SessionLocal()

    try:
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
                stream_url="/app/traffic.mp4",   # FIX: sesuai volume mount docker-compose
                
                # --- PERBAIKAN ARSITEKTUR GARIS KANVAS ---
                line_x1=100,
                line_y1=300,
                line_x2=500,
                line_y2=300,
                
                # --- PERBAIKAN PENGATURAN AI ---
                low_density_threshold=0.40,
                high_density_threshold=0.70,
                confidence_tolerance=0.50
            )
            db.add(default_camera)
            db.commit()
            print("✅ Default kamera (CAM-01) berhasil ditambahkan ke database")
        else:
            # FIX: update stream_url jika kamera sudah ada tapi stream_url-nya salah/NULL
            if not existing.stream_url or existing.stream_url == "/app/videos/traffic.mp4":
                existing.stream_url = "/app/traffic.mp4"
                db.commit()
                print("✅ stream_url CAM-01 diupdate ke /app/traffic.mp4")
            else:
                print("ℹ️  Kamera CAM-01 sudah ada di database")

    except Exception as e:
        print(f"❌ Error saat inisialisasi kamera: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_default_cameras()