"""
Smart Traffic Monitoring System (STMS) — Stream Router

Provides MJPEG streaming endpoint untuk real-time camera feeds.
Endpoint: GET /api/v1/stream/{camera_id}

FIXED: Implemented complete streaming functionality with error handling
"""

import logging
import cv2
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_db, get_stream_user

logger = logging.getLogger("stms.stream")
router = APIRouter(prefix="/api/v1/stream", tags=["Stream"])


def generate_mjpeg_frames(stream_url: str):
    """
    Generator function that yields MJPEG frame boundaries and JPEG data.
    
    Args:
        stream_url: Path or URL to video source (file path, IP camera, etc.)
    
    Yields:
        MJPEG-formatted byte chunks (boundary + header + frame data)
    """
    cap = None
    try:
        cap = cv2.VideoCapture(stream_url)
        if not cap or not cap.isOpened():
            logger.error(f"Failed to open stream: {stream_url}")
            yield b"--frame\r\n"
            yield b"Content-Type: text/plain\r\n\r\n"
            yield b"Error: Cannot open stream"
            return

        logger.info(f"Stream opened: {stream_url}")
        frame_count = 0

        while True:
            try:
                ret, frame = cap.read()
                
                if not ret or frame is None:
                    logger.debug(f"End of stream or read failed after {frame_count} frames")
                    break

                # Resize frame untuk reduce bandwidth (optional)
                # frame = cv2.resize(frame, (640, 480))

                # Encode frame as JPEG
                ret_encode, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                if not ret_encode:
                    logger.warning("Failed to encode frame")
                    continue

                frame_bytes = buffer.tobytes()
                frame_count += 1

                # Yield MJPEG frame
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n'
                    b'Content-Disposition: inline\r\n'
                    b'\r\n'
                    + frame_bytes
                    + b'\r\n'
                )

                # Limit fps to reduce CPU (optional: add sleep here)
                # time.sleep(0.033)  # ~30 fps

            except Exception as e:
                logger.error(f"Error processing frame: {e}")
                continue

    except Exception as e:
        logger.exception(f"Error in MJPEG generator: {e}")
        yield b"--frame\r\nContent-Type: text/plain\r\n\r\nError: " + str(e).encode()
    finally:
        if cap:
            cap.release()
            logger.info("Stream closed")


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/stream/{camera_id} — Live camera stream (MJPEG format)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{camera_id}")
def get_camera_stream(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: models.UserAccount = Depends(get_stream_user),  # ← ganti ini
):
    """
    Get live camera stream in MJPEG format.
    
    Args:
        camera_id: Camera ID (e.g., "CAM-001")
        
    Returns:
        StreamingResponse with MJPEG video stream
        
    Headers:
        Authorization: Bearer {JWT_TOKEN}
        
    Example:
        GET /api/v1/stream/CAM-001
        Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
        
        Response: multipart/x-mixed-replace video stream
    """
    # Fetch camera from database
    db_camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()

    if not db_camera:
        raise HTTPException(
            status_code=404,
            detail=f"Camera '{camera_id}' not found"
        )

    if db_camera.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Camera '{camera_id}' is not active (status: {db_camera.status})"
        )

    # Get stream URL from camera config
    stream_url = db_camera.stream_url
    
    if not stream_url:
        raise HTTPException(
            status_code=400,
            detail=f"Camera '{camera_id}' has no stream URL configured"
        )

    logger.info(f"Starting stream for camera {camera_id}: {stream_url}")

    # Return streaming response
    return StreamingResponse(
        generate_mjpeg_frames(stream_url),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/stream/health — Health check for streaming service
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
def stream_health():
    """Quick health check for streaming service."""
    return {
        "status": "ok",
        "service": "Stream Server",
        "endpoint": "/api/v1/stream/{camera_id}"
    }