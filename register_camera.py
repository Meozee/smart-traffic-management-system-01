#!/usr/bin/env python3
"""
Script untuk mendaftarkan kamera ke backend
"""
import requests
import json

# Backend API URL
API_URL = "http://localhost:8000/api/v1"

# Data kamera yang akan didaftarkan
camera_data = {
    "camera_id": "CAM-01",
    "location_name": "Central Aceh - Main Road",
    "segment_id": "SEG-01",
    "road_capacity": 100,
    "status": "active",
    "stream_url": "/app/videos/traffic.mp4",  # Path di dalam Docker container
    "virtual_line_y": 300
}

def register_camera():
    """Daftarkan kamera ke backend"""
    try:
        print(f"📹 Mendaftarkan kamera: {camera_data['camera_id']}...")
        response = requests.post(
            f"{API_URL}/cameras/",
            json=camera_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print("✅ Kamera berhasil didaftarkan!")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❌ Gagal mendaftarkan kamera. Status: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Pastikan backend sudah berjalan: docker-compose up -d")

if __name__ == "__main__":
    register_camera()
