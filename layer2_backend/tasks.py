"""
Background Tasks for STMS

Periodic jobs yang dijalankan oleh APScheduler:
- calculate_density_task: Kalkulasi traffic density setiap interval (default: 15 menit)
  Tahapan:
  1. Query deteksi dari interval terakhir
  2. Agregasi per camera
  3. Hitung density ratio & level
  4. Simpan ke tabel TRAFFIC_DENSITY
  5. Jika level = 'High', buat ALERT (enforce 1:1 relation)
"""

from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import func
from . import database, models, config


def calculate_density_task() -> None:
    """
    Background job untuk kalkulasi traffic density setiap interval.
    
    Dijalankan setiap DENSITY_INTERVAL_MINUTES (dari config).
    
    Process:
    1. Ambil semua camera yang aktif
    2. Untuk setiap camera:
       - Query deteksi dalam interval terakhir
       - Hitung total vehicles, inflow, outflow
       - Hitung density ratio = total / road_capacity
       - Tentukan density level (Low/Medium/High) berdasarkan threshold
       - Simpan TRAFFIC_DENSITY record
       - Jika level = 'High', check apakah density_id sudah ada alert
         (enforce relasi 1:1 TRAFFIC_DENSITY → ALERT)
       - Jika belum ada, buat ALERT baru
    
    Semua timestamp menggunakan UTC timezone.
    """
    
    db = database.SessionLocal()
    
    try:
        print(f"\n🔄 [BACKGROUND JOB] Calculating traffic density at {datetime.now(timezone.utc).isoformat()}")
        
        # Calculate time window untuk interval sebelumnya
        now = datetime.now(timezone.utc)
        interval_start = now - timedelta(minutes=config.DENSITY_INTERVAL_MINUTES)
        interval_end = now
        
        # Query semua camera yang aktif
        cameras = db.query(models.Camera).filter(
            models.Camera.status == 'active'
        ).all()
        
        if not cameras:
            print("⚠️  [BACKGROUND JOB] No active cameras found.")
            return
        
        density_records_created = 0
        alerts_created = 0
        
        # Process setiap camera
        for camera in cameras:
            # Query detections dalam interval ini
            detections = db.query(models.VehicleDetection).filter(
                models.VehicleDetection.camera_id == camera.camera_id,
                models.VehicleDetection.timestamp >= interval_start,
                models.VehicleDetection.timestamp <= interval_end
            ).all()
            
            # Agregasi: count total, inflow, outflow
            total_vehicles = len(detections)
            inflow_count = len([d for d in detections if d.direction == 'Inbound'])
            outflow_count = len([d for d in detections if d.direction == 'Outbound'])
            
            # Hitung density ratio
            if camera.road_capacity > 0:
                density_ratio = total_vehicles / camera.road_capacity
            else:
                density_ratio = 0.0
            
            # Clamp ratio ke [0.0, 1.0]
            density_ratio = min(max(density_ratio, 0.0), 1.0)
            
            # Tentukan density level berdasarkan config thresholds
            if density_ratio < config.DENSITY_LOW_THRESHOLD:
                density_level = "Low"
            elif density_ratio < config.DENSITY_HIGH_THRESHOLD:
                density_level = "Medium"
            else:
                density_level = "High"
            
            # Check apakah sudah ada TRAFFIC_DENSITY record untuk interval ini
            # (prevent duplikasi jika job dijalankan 2x dalam interval yang sama)
            existing_density = db.query(models.TrafficDensity).filter(
                models.TrafficDensity.camera_id == camera.camera_id,
                models.TrafficDensity.interval_start == interval_start,
                models.TrafficDensity.interval_end == interval_end
            ).first()
            
            if existing_density:
                # Update existing record
                existing_density.total_vehicles = total_vehicles
                existing_density.inflow_count = inflow_count
                existing_density.outflow_count = outflow_count
                existing_density.density_ratio = density_ratio
                existing_density.density_level = density_level
                db.commit()
                density_id = existing_density.density_id
            else:
                # Create new TRAFFIC_DENSITY record
                new_density = models.TrafficDensity(
                    camera_id=camera.camera_id,
                    interval_start=interval_start,
                    interval_end=interval_end,
                    total_vehicles=total_vehicles,
                    inflow_count=inflow_count,
                    outflow_count=outflow_count,
                    density_ratio=density_ratio,
                    density_level=density_level
                )
                db.add(new_density)
                db.commit()
                db.refresh(new_density)
                density_id = new_density.density_id
                density_records_created += 1
            
            # ═══════════════════════════════════════════════════════════════════════════
            # UC-08: ALERT ENGINE
            # ═══════════════════════════════════════════════════════════════════════════
            
            if density_level == "High":
                # Check apakah density_id sudah punya alert (enforce 1:1 relation)
                existing_alert = db.query(models.Alert).filter(
                    models.Alert.density_id == density_id
                ).first()
                
                if not existing_alert:
                    # Create new ALERT untuk HIGH density
                    alert_message = (
                        f"⚠️ PERINGATAN: Kepadatan lalu lintas TINGGI terdeteksi di "
                        f"{camera.location_name} ({camera.camera_id}). "
                        f"Density level: {density_level} ({density_ratio*100:.1f}% dari kapasitas jalan). "
                        f"Inflow: {inflow_count}, Outflow: {outflow_count} kendaraan."
                    )
                    
                    new_alert = models.Alert(
                        density_id=density_id,
                        camera_id=camera.camera_id,
                        triggered_at=datetime.now(timezone.utc),
                        density_level=density_level,
                        alert_type="High Density",
                        severity="High",
                        message=alert_message,
                        acknowledged=False
                    )
                    
                    db.add(new_alert)
                    db.commit()
                    alerts_created += 1
                    
                    print(f"🚨 [ALERT] {camera.camera_id}: HIGH density detected!")
        
        print(
            f"✅ [BACKGROUND JOB] Completed: "
            f"{density_records_created} density records, "
            f"{alerts_created} alerts created"
        )
    
    except Exception as e:
        print(f"❌ [BACKGROUND JOB] Error: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()