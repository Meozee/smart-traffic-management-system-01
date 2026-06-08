"""
stream.py
Layer 2 — Live Stream Router

FUNGSI BARU (FIXED ARCHITECTURE):
Hanya berfungsi sebagai penyalur video mentah (MJPEG stream) ke Frontend.
Proses YOLO, Tracking, dan Database Write DIHAPUS dari sini karena 
sudah ditangani secara independen oleh Layer 1 (cv_module.py).
Ini mencegah CPU/GPU overhead pada server FastAPI.
"""

import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from .. import models, database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Live Stream"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_frames(stream_url: str):
    """
    Generator murni untuk MJPEG stream. 
    Tidak ada AI / YOLO di sini. Sangat ringan untuk server.
    """
    if not stream_url:
        logger.error("stream_url kosong")
        return

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        logger.error(f"Gagal membuka stream: {stream_url}")
        return

    try:
        while True:
            success, frame = cap.read()

            # Jika file video habis (untuk testing mp4), ulang dari awal
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
                if not success:
                    break

            # Encode frame mentah ke JPEG
            ret, buffer = cv2.imencode(".jpg", frame)
            if not ret:
                continue

            # Kirim frame ke browser
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
    """Endpoint untuk dipanggil oleh tag <img> di dashboard frontend Bima."""
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
        generate_frames(camera.stream_url),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )