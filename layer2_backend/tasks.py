from datetime import datetime, timedelta
from . import database, models

def calculate_density_task():
    print("🔄 [BACKGROUND JOB] Memulai perhitungan densitas lalu lintas...")
    db = database.SessionLocal()
    try:
        now = datetime.now()
        interval_start = now - timedelta(minutes=15)
        
        cameras = db.query(models.Camera).all()

        for cam in cameras:
            detections = db.query(models.VehicleDetection).filter(
                models.VehicleDetection.camera_id == cam.camera_id,
                models.VehicleDetection.timestamp >= interval_start
            ).all()

            total = len(detections)
            inflow = len([d for d in detections if d.direction == 'inbound'])
            outflow = len([d for d in detections if d.direction == 'outbound'])

            ratio = (total / cam.road_capacity) * 100 if cam.road_capacity > 0 else 0
            level = "LOW" if ratio < 30 else ("MEDIUM" if ratio < 70 else "HIGH")

            # Simpan ke TrafficDensity
            new_density = models.TrafficDensity(
                camera_id=cam.camera_id,
                interval_start=interval_start,
                interval_end=now,
                total_vehicles=total,
                inflow_count=inflow,
                outflow_count=outflow,
                density_ratio=round(ratio, 2),
                density_level=level
            )
            db.add(new_density)

            # --- [UC-08: ALERT SYSTEM] ---
            # Jika level HIGH, buat entry di tabel alert
            if level == "HIGH":
                alert_msg = f"Peringatan: Kepadatan tinggi ({ratio:.1f}%) terdeteksi di {cam.location_name}."
                new_alert = models.Alert(
                    camera_id=cam.camera_id,
                    message=alert_msg
                )
                db.add(new_alert)
        
        db.commit()
        print("✅ [BACKGROUND JOB] Perhitungan & Pengecekan Alert selesai!")
    except Exception as e:
        print(f"❌ Error Job: {e}")
        db.rollback()
    finally:
        db.close()