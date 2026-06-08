import os
import time
import requests
import logging
from cv_module import VideoCapture, VehicleDetector

logger = logging.getLogger("stms.cv")
logging.basicConfig(level=logging.INFO)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "secret_key") # Samakan dengan backend
CAMERA_ID = "CAM-001"
MODEL_PATH = "yolov8n.pt"

def get_camera_config() -> dict:
    """Mengambil koordinat garis dari Backend API, BUKAN dari Database langsung."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/cameras/")
        if response.status_code == 200:
            cameras = response.json()
            for cam in cameras:
                if cam["camera_id"] == CAMERA_ID:
                    return cam
    except Exception as e:
        logger.error(f"Gagal mengambil config kamera: {e}")
    
    # Fallback default jika API mati
    return {"line_x1": 100, "line_y1": 300, "line_x2": 500, "line_y2": 300, "stream_url": "traffic.mp4"}

def send_detection_to_api(det_dict: dict) -> None:
    """Mengirim data mobil menyeberang ke Backend API."""
    try:
        headers = {"X-Internal-Key": INTERNAL_KEY}
        det_dict["camera_id"] = CAMERA_ID
        res = requests.post(f"{API_BASE_URL}/api/v1/detections/", json=det_dict, headers=headers)
        if res.status_code == 200:
            logger.info(f"Berhasil mencatat {det_dict['vehicle_type']} - {det_dict['direction']}")
    except Exception as e:
        logger.error(f"Gagal kirim data ke API: {e}")

def run_detection_loop():
    config = get_camera_config()
    detector = VehicleDetector(MODEL_PATH, 0.5)
    
    # Masukkan 4 titik garis dari API ke dalam AI
    detector.set_virtual_line(
        config.get("line_x1", 100), config.get("line_y1", 300),
        config.get("line_x2", 500), config.get("line_y2", 300)
    )
    
    cap = VideoCapture(config.get("stream_url", "traffic.mp4"))
    cap.open(config.get("stream_url", "traffic.mp4"))

    while True:
        frame = cap.read_frame()
        if frame is None:
            break

        # AI Menganalisis Frame
        detections = detector.detect(cap.preprocess(frame))
        
        # Jika ada mobil yang terdeteksi menyeberang (Inbound/Outbound)
        for det in detections:
            send_detection_to_api(det.to_dict())

if __name__ == '__main__':
    run_detection_loop()