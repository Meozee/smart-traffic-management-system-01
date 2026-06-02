"""
stream.py
Layer 2 — Live Stream Router

Streams MJPEG video with YOLOv8 bounding box annotations via multipart response.
Each unique vehicle crossing the center line is recorded to vehicle_detection table.

FIX:
- direction values capitalized: "inbound" → "Inbound", "outbound" → "Outbound"
  to match DB CHECK constraint and rest of codebase (Inbound/Outbound)
- Added NULL check for stream_url before opening VideoCapture
- Added loop restart for video files (rewinds when traffic.mp4 ends)
- model loaded with error handling to avoid crash on missing yolov8n.pt
"""

import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .. import models, database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Live Stream"])

# Load YOLO model once at module level
try:
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    logger.info("YOLO model loaded for stream.py")
except Exception as e:
    model = None
    logger.warning(f"YOLO model not loaded in stream.py: {e}")


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_frames(camera_id: str, stream_url: str):
    """
    Generator that yields MJPEG frames with YOLO annotations.
    For video files: loops back to start when video ends.
    For live streams: stops when stream disconnects.
    """
    if not stream_url:
        logger.error(f"stream_url is None for camera {camera_id}")
        return

    if model is None:
        logger.error("YOLO model not available, cannot stream")
        return

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        logger.error(f"Cannot open stream: {stream_url}")
        return

    width    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    center_x = max(width // 2, 1)
    tracked_ids = {}

    try:
        while True:
            success, frame = cap.read()

            # Video file ended — loop back to beginning
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
                if not success:
                    break

            results = model.track(
                frame,
                persist=True,
                classes=[2, 3, 5, 7],
                conf=0.3
            )

            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                ids   = results[0].boxes.id.cpu().numpy().astype(int)
                clss  = results[0].boxes.cls.cpu().numpy().astype(int)
                confs = results[0].boxes.conf.cpu().numpy()

                for box, obj_id, cls_idx, conf in zip(boxes, ids, clss, confs):
                    cx = int((box[0] + box[2]) / 2)

                    # FIX: Capitalized to match DB constraint CHECK (direction IN ('Inbound','Outbound'))
                    direction = "Inbound" if cx < center_x else "Outbound"

                    if obj_id not in tracked_ids:
                        tracked_ids[obj_id] = direction

                        db = database.SessionLocal()
                        try:
                            new_detection = models.VehicleDetection(
                                camera_id    = camera_id,
                                timestamp    = datetime.now(timezone.utc),
                                vehicle_type = model.names[cls_idx],
                                count        = 1,
                                direction    = direction,
                                confidence   = float(conf)
                            )
                            db.add(new_detection)
                            db.commit()
                        except Exception as e:
                            db.rollback()
                            logger.warning(f"Failed to save detection: {e}")
                        finally:
                            db.close()

            # Draw annotations
            visual_frame = results[0].plot()
            cv2.line(visual_frame, (center_x, 0), (center_x, frame.shape[0]), (255, 255, 0), 2)
            cv2.putText(visual_frame, "INBOUND",  (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(visual_frame, "OUTBOUND", (center_x + 20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            ret, buffer = cv2.imencode(".jpg", visual_frame)
            if not ret:
                continue

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n'
                + buffer.tobytes()
                + b'\r\n'
            )
    finally:
        cap.release()


@router.get("/stream/{camera_id}")
def video_feed(camera_id: str, db: Session = Depends(get_db)):
    """Stream MJPEG video with YOLO annotations for the given camera."""
    camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()

    if not camera:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")

    if not camera.stream_url:
        raise HTTPException(
            status_code=422,
            detail=f"stream_url untuk kamera {camera_id} belum dikonfigurasi."
        )

    return StreamingResponse(
        generate_frames(camera.camera_id, camera.stream_url),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )