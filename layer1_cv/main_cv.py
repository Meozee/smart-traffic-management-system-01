"""
Smart Traffic Monitoring System (STMS) — CV Layer Main Module

Entry point TUNGGAL untuk Layer 1 (Computer Vision).

Responsibilities:
1. Connect to camera config via /internal/config (menggunakan X-Internal-Key)
2. Run YOLOv8 tracking (menggunakan raw frame, tanpa preprocess manual)
3. Send detection events to backend API (menggunakan X-Internal-Key)
"""

import os
import time
import requests
import logging
from cv_module import VideoCapture, VehicleDetector

logger = logging.getLogger("stms.cv")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "stms-internal-key-2025")
CAMERA_ID = os.getenv("CAMERA_ID", "CAM-01")  # Sesuaikan dengan default di backend
MODEL_PATH = os.getenv("MODEL_PATH", "weights/yolov8n.pt") # Arahkan ke folder weights
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))

logger.info("Configuration:")
logger.info(f"  API_BASE_URL: {API_BASE_URL}")
logger.info(f"  CAMERA_ID: {CAMERA_ID}")
logger.info(f"  MODEL_PATH: {MODEL_PATH}")
logger.info(f"  CONFIDENCE_THRESHOLD: {CONFIDENCE_THRESHOLD}")


# ═══════════════════════════════════════════════════════════════════════════════
# API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_camera_config() -> dict:
    """Fetch camera config via /internal/config (tanpa JWT)."""
    try:
        headers = {"X-Internal-Key": INTERNAL_API_KEY}
        
        response = requests.get(
            f"{API_BASE_URL}/api/v1/cameras/internal/config",
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            cameras = response.json()
            for cam in cameras:
                # Pastikan kamera cocok dan statusnya active
                if cam.get("camera_id") == CAMERA_ID and cam.get("status") == "active":
                    logger.info(f"✅ Fetched config for active camera: {CAMERA_ID}")
                    return cam
            
            logger.warning(f"Kamera {CAMERA_ID} tidak ditemukan atau statusnya tidak 'active'")
        else:
            logger.error(f"API returned {response.status_code}: {response.text}")
    
    except Exception as e:
        logger.error(f"Error fetching camera config: {e}")

    # Fallback to defaults if API unavailable
    logger.warning("Menggunakan konfigurasi darurat (Fallback)")
    return {
        "camera_id": CAMERA_ID,
        "stream_url": "traffic.mp4",
        "line_x1": 100,
        "line_y1": 300,
        "line_x2": 500,
        "line_y2": 300,
    }


def send_detection_to_api(detection_dict: dict) -> bool:
    """Send detection event via /detections/ (tanpa JWT)."""
    try:
        headers = {
            "X-Internal-Key": INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        
        if "camera_id" not in detection_dict:
            detection_dict["camera_id"] = CAMERA_ID
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/detections/",
            json=detection_dict,
            headers=headers,
            timeout=2
        )
        
        if response.status_code == 200:
            logger.info(f"🚀 {detection_dict.get('vehicle_type')} menyeberang ke arah {detection_dict.get('direction')} -> Terkirim!")
            return True
        else:
            logger.error(f"Gagal mengirim data: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error mengirim deteksi: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def run_detection_loop():
    logger.info("🚀 Memulai Layer 1 AI (Computer Vision)...")
    
    # 1. Ambil Config dari Backend
    config = get_camera_config()
    
    # 2. Inisialisasi AI (Otak)
    detector = VehicleDetector(MODEL_PATH, CONFIDENCE_THRESHOLD)
    detector.set_virtual_line(
        config.get("line_x1", 100),
        config.get("line_y1", 300),
        config.get("line_x2", 500),
        config.get("line_y2", 300)
    )
    
    stream_url = config.get("stream_url", "traffic.mp4")
    
    # 3. Buka Kamera dengan Context Manager (Sangat Aman)
    with VideoCapture(stream_url, auto_open=True) as cap:
        if cap.cap is None or not cap.cap.isOpened():
            logger.error(f"❌ Gagal membuka stream dari: {stream_url}")
            return
            
        logger.info(f"✅ Mata AI Terbuka! Memantau: {stream_url}")
        
        frame_count = 0
        detection_count = 0
        
        try:
            while True:
                # 4. Baca Gambar
                frame = cap.read_frame()
                if frame is None:
                    logger.warning("⚠️ Video stream terputus atau selesai.")
                    break
                
                frame_count += 1
                
                # 5. Deteksi Kendaraan (Bypass preprocess manual, langsung lempar frame mentah)
                detections = detector.detect(frame)
                
                # 6. Kirim Laporan ke Backend
                for det in detections:
                    if send_detection_to_api(det.to_dict()):
                        detection_count += 1
                
                # Jeda tipis untuk menghindari pemborosan CPU
                time.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("🛑 Dihentikan paksa oleh pengguna.")
        except Exception as e:
            logger.exception(f"Error fatal di main loop: {e}")
        finally:
            logger.info(f"🏁 Sesi selesai. Total Frame diproses: {frame_count}, Deteksi terkirim: {detection_count}")


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("STMS - Computer Vision Node Aktif")
    logger.info("=" * 60)
    run_detection_loop()