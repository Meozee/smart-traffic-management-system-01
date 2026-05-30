"""
main_cv.py
Entry point for Layer 1 – Computer Vision Module.

Runs detection loop, aggregates density, saves to DB and dispatches alerts.
"""

import sys
import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional, List

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv_module import VideoCapture, VehicleDetector, Detection
from density_calculator import DensityCalculator
from alert_engine import AlertEngine

logger = logging.getLogger("stms.cv")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

try:
    from layer2_backend.config import MODEL_PATH, CONFIDENCE_THRESHOLD, DENSITY_INTERVAL_MINUTES
    from layer2_backend.database import SessionLocal
    from layer2_backend import models
except Exception:
    MODEL_PATH = os.getenv('MODEL_PATH', 'yolov8n.pt')
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.5'))
    DENSITY_INTERVAL_MINUTES = int(os.getenv('DENSITY_INTERVAL_MINUTES', '15'))
    SessionLocal = None
    models = None
    logger.warning("Cannot import layer2_backend modules; running in standalone mode.")

VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "traffic.mp4")
CAMERA_ID = os.getenv("CAMERA_ID", "CAM-001")
ROAD_CAPACITY = int(os.getenv("ROAD_CAPACITY", "100"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
RETRY_DELAY_SECONDS = 5


def get_camera_config(camera_id: str) -> dict:
    """Retrieve camera config from DB; fallback to env values if DB unavailable."""
    if SessionLocal is None or models is None:
        return {"road_capacity": ROAD_CAPACITY, "video_source": VIDEO_SOURCE}
    session = SessionLocal()
    try:
        cam = session.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
        if not cam:
            return {"road_capacity": ROAD_CAPACITY, "video_source": VIDEO_SOURCE}
        # stream_url may be used as source if present
        source = getattr(cam, 'stream_url', None) or VIDEO_SOURCE
        return {"road_capacity": int(cam.road_capacity), "video_source": source}
    except Exception:
        logger.exception("Error fetching camera config from DB; using defaults")
        return {"road_capacity": ROAD_CAPACITY, "video_source": VIDEO_SOURCE}
    finally:
        session.close()


def save_detections_to_db(detections: List[Detection], camera_id: str) -> None:
    """Persist Detection objects to vehicle_detection table via SQLAlchemy ORM."""
    if SessionLocal is None or models is None:
        logger.debug("DB not available; skipping save_detections_to_db")
        return
    session = SessionLocal()
    try:
        for det in detections:
            if not hasattr(det, 'to_dict'):
                continue
            d = models.VehicleDetection(
                camera_id=camera_id,
                timestamp=datetime.fromisoformat(det.timestamp.isoformat()),
                vehicle_type=det.vehicle_type,
                count=1,
                direction=det.direction_flow,
                bbox_data={"bbox": det.bbox},
                confidence=float(det.confidence) if det.confidence is not None else None
            )
            session.add(d)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Error saving detections to DB")
    finally:
        session.close()


def save_density_to_db(density_record: dict) -> Optional[int]:
    """Save density_record dict to traffic_density and return density_id on success."""
    if SessionLocal is None or models is None:
        logger.debug("DB not available; skipping save_density_to_db")
        return None
    session = SessionLocal()
    try:
        rec = models.TrafficDensity(
            camera_id=density_record["camera_id"],
            interval_start=density_record["interval_start"],
            interval_end=density_record["interval_end"],
            total_vehicles=density_record["total_vehicles"],
            inflow_count=density_record["inflow_count"],
            outflow_count=density_record["outflow_count"],
            density_ratio=density_record.get("density_ratio"),
            density_level=density_record.get("density_level")
        )
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return int(rec.density_id)
    except Exception:
        session.rollback()
        logger.exception("Error saving density record to DB")
        return None
    finally:
        session.close()


def run_detection_loop(camera_id: str = CAMERA_ID) -> None:
    config = get_camera_config(camera_id)
    road_capacity = config.get("road_capacity", ROAD_CAPACITY)
    video_source = config.get("video_source", VIDEO_SOURCE)

    cap = VideoCapture(video_source)
    detector = VehicleDetector(MODEL_PATH, CONFIDENCE_THRESHOLD)
    density_calc = DensityCalculator(camera_id, road_capacity, DENSITY_INTERVAL_MINUTES)
    alert_engine = AlertEngine(API_BASE_URL)

    logger.info(f"Starting CV loop for camera {camera_id} source={video_source}")

    while not cap.open(video_source):
        logger.error(f"Failed to open source {video_source}. Retrying in {RETRY_DELAY_SECONDS}s")
        time.sleep(RETRY_DELAY_SECONDS)

    try:
        while True:
            frame = cap.read_frame()
            if frame is None:
                logger.info("Stream ended or empty frame. Stopping loop.")
                break

            pre = cap.preprocess(frame)
            if pre is None:
                continue

            detections = detector.detect(pre)
            density_calc.aggregate(detections)

            if density_calc.is_interval_elapsed():
                density_record = density_calc.to_density_record()
                logger.info(f"Interval done camera={camera_id} vehicles={density_record['total_vehicles']} level={density_record['density_level']}")

                # persist detections and density
                save_detections_to_db(detections, camera_id)
                density_id = save_density_to_db(density_record)

                if density_record['density_level'] == 'High' and density_id is not None and alert_engine.should_create_alert(density_id):
                    alert_data = alert_engine.create_alert(density_id, camera_id, 'High', density_record['total_vehicles'])
                    success = alert_engine.dispatch(alert_data)
                    if success:
                        alert_engine.mark_alerted(density_id)
                        logger.info(f"Alert dispatched for density_id={density_id}")
                    else:
                        logger.warning("Alert dispatch failed; but density saved to DB")

                density_calc.reset_counter()
    except KeyboardInterrupt:
        logger.info("CV loop interrupted by user")
    finally:
        cap.release()
        logger.info("CV module shutdown complete")


if __name__ == '__main__':
    run_detection_loop()
