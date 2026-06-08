"""
tasks.py
Background Tasks for STMS

Periodic job dijalankan oleh APScheduler setiap DENSITY_INTERVAL_MINUTES.

FIX:
1. Query detection menggunakan timestamp naive (tanpa timezone) agar kompatibel
   dengan data yang disimpan stream.py menggunakan datetime.now(timezone.utc).isoformat()
   → Semua timestamp sekarang UTC aware di kedua sisi.
2. Direction filter menggunakan 'Inbound'/'Outbound' (kapital) sesuai stream.py fixed.
3. Duplicate check interval menggunakan BETWEEN range, bukan exact timestamp match.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from . import database, models, config
import logging

logger = logging.getLogger(__name__)


def calculate_density_task() -> None:
    """
    Background job: kalkulasi traffic density setiap interval.

    Process per camera aktif:
    1. Query detections dalam interval terakhir
    2. Hitung total, inflow, outflow
    3. Hitung density ratio & level
    4. Simpan/update TRAFFIC_DENSITY
    5. Buat ALERT jika level == 'High' dan belum ada alert untuk density ini
    """
    db = database.SessionLocal()

    try:
        now            = datetime.now(timezone.utc)
        interval_end   = now
        interval_start = now - timedelta(minutes=config.DENSITY_INTERVAL_MINUTES)

        logger.info(f"[DENSITY JOB] Running at {now.isoformat()}")
        logger.info(f"[DENSITY JOB] Window: {interval_start.isoformat()} → {interval_end.isoformat()}")

        cameras = db.query(models.Camera).filter(
            models.Camera.status == 'active'
        ).all()

        if not cameras:
            logger.warning("[DENSITY JOB] No active cameras found.")
            return

        density_created = 0
        alerts_created  = 0

        for camera in cameras:
            # ── Query detections dalam interval ──────────────────────────────
            # FIX: gunakan func.timezone untuk handle naive vs aware timestamp
            # PostgreSQL menyimpan TIMESTAMP (tanpa tz), compare dengan UTC aware
            detections = db.query(models.VehicleDetection).filter(
                models.VehicleDetection.camera_id == camera.camera_id,
                models.VehicleDetection.timestamp >= interval_start.replace(tzinfo=None),
                models.VehicleDetection.timestamp <= interval_end.replace(tzinfo=None)
            ).all()

            total_vehicles = len(detections)

            # FIX: 'Inbound'/'Outbound' — kapital, sesuai stream.py fixed
            inflow_count  = sum(1 for d in detections if d.direction == 'Inbound')
            outflow_count = sum(1 for d in detections if d.direction == 'Outbound')

            # Hitung density ratio, clamp ke [0.0, 1.0]
            if camera.road_capacity and camera.road_capacity > 0:
                density_ratio = min(total_vehicles / camera.road_capacity, 1.0)
            else:
                density_ratio = 0.0

            # Klasifikasi level
            if density_ratio < camera.low_density_threshold:
                density_level = "Low"
            elif density_ratio < camera.high_density_threshold:
                density_level = "Medium"
            else:
                density_level = "High"

            logger.info(
                f"[DENSITY JOB] {camera.camera_id}: "
                f"total={total_vehicles}, ratio={density_ratio:.2f}, level={density_level}"
            )

            # ── Cek duplikat menggunakan OVERLAPPING range, bukan exact match ─
            # FIX: cek apakah sudah ada record yang interval-nya overlap dengan window ini
            existing = db.query(models.TrafficDensity).filter(
                models.TrafficDensity.camera_id      == camera.camera_id,
                models.TrafficDensity.interval_start == interval_start.replace(tzinfo=None),
            ).first()

            if existing:
                # Update existing record
                existing.total_vehicles = total_vehicles
                existing.inflow_count   = inflow_count
                existing.outflow_count  = outflow_count
                existing.density_ratio  = density_ratio
                existing.density_level  = density_level
                db.commit()
                density_id = existing.density_id
                logger.info(f"[DENSITY JOB] Updated density_id={density_id}")
            else:
                # Buat record baru
                new_density = models.TrafficDensity(
                    camera_id      = camera.camera_id,
                    interval_start = interval_start.replace(tzinfo=None),
                    interval_end   = interval_end.replace(tzinfo=None),
                    total_vehicles = total_vehicles,
                    inflow_count   = inflow_count,
                    outflow_count  = outflow_count,
                    density_ratio  = density_ratio,
                    density_level  = density_level
                )
                db.add(new_density)
                db.commit()
                db.refresh(new_density)
                density_id = new_density.density_id
                density_created += 1
                logger.info(f"[DENSITY JOB] Created density_id={density_id}")

            # ── Alert jika High density ───────────────────────────────────────
            if density_level == "High":
                existing_alert = db.query(models.Alert).filter(
                    models.Alert.density_id == density_id
                ).first()

                if not existing_alert:
                    alert_msg = (
                        f"Kepadatan lalu lintas TINGGI terdeteksi di "
                        f"{camera.location_name} ({camera.camera_id}). "
                        f"Density: {density_ratio*100:.1f}% dari kapasitas. "
                        f"Total: {total_vehicles} kendaraan "
                        f"(Inflow: {inflow_count}, Outflow: {outflow_count})."
                    )
                    new_alert = models.Alert(
                        density_id    = density_id,
                        camera_id     = camera.camera_id,
                        triggered_at  = datetime.now(timezone.utc).replace(tzinfo=None),
                        density_level = density_level,
                        alert_type    = "High Density",
                        severity      = "High",
                        message       = alert_msg,
                        acknowledged  = False
                    )
                    db.add(new_alert)
                    db.commit()
                    alerts_created += 1
                    logger.info(f"[DENSITY JOB] Alert created for {camera.camera_id}")

        logger.info(
            f"[DENSITY JOB] Done: "
            f"{density_created} records created, {alerts_created} alerts created"
        )

    except Exception as e:
        logger.exception(f"[DENSITY JOB] Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()