"""
run_ai.py
Eksekutor Utama Layer 1 (Computer Vision)
Telah diperbarui: Auto-Login & Auto-Detect Active Camera.
"""

import cv2
import time
import requests
from datetime import datetime, timezone
from cv_module import VideoCapture, VehicleDetector

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

def get_auth_token():
    print("🔐 Meminta izin akses ke Backend (Login sebagai AI)...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login", 
            data={"username": "admin", "password": "miko"},
            timeout=5
        )
        if response.status_code == 200:
            print("✅ Izin Akses Diberikan!")
            return response.json().get("access_token")
        else:
            print(f"⚠️ Login gagal ({response.status_code}).")
            return None
    except requests.exceptions.Timeout:
        print("❌ Server Backend TIDAK MERESPONS selama 5 detik!")
        return None
    except Exception as e:
        print(f"❌ Error koneksi ke Backend: {e}")
        return None

def run():
    print("🚀 Memulai Layer 1 AI...")

    # 1. Ambil Token Akses
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # 2. Ambil data SEMUA kamera dari Backend
    try:
        response = requests.get(f"{API_BASE_URL}/cameras/", headers=headers, timeout=5)
        if response.status_code != 200:
            print(f"❌ Ditolak oleh Backend! Status: {response.status_code}")
            return
        
        cameras = response.json()
        
        # 🔥 LOGIKA CERDAS: Cari SATU kamera yang statusnya "active" dan punya URL
        cam_data = next((c for c in cameras if c.get("status") == "active" and c.get("stream_url")), None)
        
        if not cam_data:
            print("❌ Tidak ada satupun kamera berstatus 'active' dengan Stream URL di Database.")
            print("💡 Solusi: Buka Dashboard > Settings > Buat/Edit kamera dan pastikan statusnya Active.")
            return

    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # 3. Ekstrak data kamera aktif yang ditemukan
    CAMERA_ID = cam_data["camera_id"]
    stream_url = cam_data["stream_url"]

    print(f"🎯 Kamera Aktif Ditemukan: {CAMERA_ID}")
    print(f"📡 Terhubung ke stream: {stream_url}")

    # 4. Inisialisasi AI YOLOv8
    detector = VehicleDetector("yolov8n.pt")
    
    detector.set_virtual_line(
        cam_data.get("line_x1", 100),
        cam_data.get("line_y1", 300),
        cam_data.get("line_x2", 500),
        cam_data.get("line_y2", 300)
    )

    cap = VideoCapture(stream_url)
    if not cap.open(stream_url):
        print(f"❌ Gagal membuka video stream dari {stream_url}. Pastikan HP menyala dan IP benar.")
        return

    print("✅ AI Aktif! Mata sistem terbuka dan sedang memantau lalu lintas...")

    # 5. Main Loop Deteksi
    while True:
        frame = cap.read_frame()
        if frame is None:
            print("⚠️ Video stream terputus.")
            break

        detections = detector.detect(frame)

        for det in detections:
            print(f"🚗 {det.vehicle_type} terdeteksi menyeberang ke arah {det.direction_flow}!")
            
            payload = {
                "camera_id": CAMERA_ID,
                "timestamp": det.timestamp.isoformat(),
                "vehicle_type": det.vehicle_type,
                "count": 1,
                "direction": det.direction_flow,
                "confidence": det.confidence
            }
            
            try:
                res = requests.post(f"{API_BASE_URL}/detections/", json=payload, headers=headers, timeout=2)
                if res.status_code in [404, 307]:
                     res = requests.post(f"{API_BASE_URL}/detections", json=payload, headers=headers, timeout=2)
            except Exception:
                pass

        time.sleep(0.01)

if __name__ == "__main__":
    run()