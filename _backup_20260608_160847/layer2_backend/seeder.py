"""
STMS Data Seeder - Prototype Traffic Trend Analysis
Menyuntikkan data dummy (TrafficDensity, VehicleDetection, Alerts) selama 7 hari terakhir
agar grafik di Dashboard dan Reports terlihat realistis.
"""

import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Camera, TrafficDensity, Alert, VehicleDetection

def generate_realistic_traffic(hour: int, capacity: int) -> int:
    """Membuat pola lalu lintas yang realistis berdasarkan jam."""
    if 0 <= hour < 5:      # Tengah malam (Sepi)
        return random.randint(5, int(capacity * 0.2))
    elif 6 <= hour < 9:    # Jam berangkat kerja (Sangat Padat)
        return random.randint(int(capacity * 0.6), int(capacity * 0.95))
    elif 9 <= hour < 15:   # Siang hari (Normal)
        return random.randint(int(capacity * 0.3), int(capacity * 0.5))
    elif 16 <= hour < 19:  # Jam pulang kerja (Sangat Padat)
        return random.randint(int(capacity * 0.7), int(capacity * 1.1)) # Bisa overcapacity
    else:                  # Malam hari (Mulai sepi)
        return random.randint(int(capacity * 0.2), int(capacity * 0.4))

def run_seeder():
    db: Session = SessionLocal()
    try:
        # 1. Ambil Kamera Aktif Pertama (Misal CAM-01)
        camera = db.query(Camera).filter(Camera.status == "active").first()
        if not camera:
            print("❌ Tidak ada kamera aktif. Daftarkan kamera di Settings dulu.")
            return

        capacity = camera.road_capacity if camera.road_capacity else 100
        low_thr = camera.low_density_threshold
        high_thr = camera.high_density_threshold

        print(f"💉 Memulai injeksi data untuk kamera {camera.camera_id}...")
        
        # 2. Hapus data lama agar tidak menumpuk ganda jika script dijalankan berkali-kali
        db.query(Alert).delete()
        db.query(TrafficDensity).delete()
        db.query(VehicleDetection).delete()
        db.commit()

        # 3. Setup Waktu (Mundur 7 Hari)
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=7)
        
        current_time = start_date
        interval_minutes = 15
        
        densities = []
        alerts = []
        
        while current_time <= now:
            end_time = current_time + timedelta(minutes=interval_minutes)
            
            # Hitung kendaraan
            total_vehicles = generate_realistic_traffic(current_time.hour, capacity)
            inflow = int(total_vehicles * random.uniform(0.4, 0.6))
            outflow = total_vehicles - inflow
            
            ratio = min(total_vehicles / capacity, 1.0)
            
            # Tentukan Level
            if ratio >= high_thr:
                level = "High"
            elif ratio >= low_thr:
                level = "Medium"
            else:
                level = "Low"
                
            # Buat Record Density
            density = TrafficDensity(
                camera_id=camera.camera_id,
                interval_start=current_time,
                interval_end=end_time,
                total_vehicles=total_vehicles,
                inflow_count=inflow,
                outflow_count=outflow,
                density_ratio=ratio,
                density_level=level
            )
            densities.append(density)
            
            # Lanjut ke interval 15 menit berikutnya
            current_time = end_time

        # Simpan Densities ke DB
        db.bulk_save_objects(densities)
        db.commit()
        
        # 4. Buat Alerts untuk yang High Density
        saved_densities = db.query(TrafficDensity).filter(TrafficDensity.density_level == "High").all()
        for d in saved_densities:
            alert = Alert(
                density_id=d.density_id,
                camera_id=d.camera_id,
                triggered_at=d.interval_start,
                density_level="High",
                message=f"Kemacetan terdeteksi di {camera.location_name}! ({d.total_vehicles} kendaraan)",
                acknowledged=random.choice([True, False]) # Random ack status
            )
            alerts.append(alert)
            
        db.bulk_save_objects(alerts)
        db.commit()
        
        print(f"✅ Injeksi selesai! Berhasil menambahkan {len(densities)} rekam jejak lalu lintas dan {len(alerts)} peringatan kemacetan.")

    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_seeder()