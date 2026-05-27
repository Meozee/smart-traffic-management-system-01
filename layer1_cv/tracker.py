import cv2
import requests
from ultralytics import YOLO
from datetime import datetime

# ==================================================
# PILIH SUMBER VIDEO
# ==================================================

# ====== VIDEO FILE ======
# source = "tests/sample_video1.mp4"
# s_id = "VID-01"

# ====== DROIDCAM / HP ======
# source = "http://192.168.100.249:4747/video"
# s_id = "PHN-01"

# ====== VIDEO FILE LOKAL ======
source = "traffic.mp4"
s_id = "CAM-01"

# ====== CCTV RTSP ======
# source = "rtsp://admin:password@192.168.1.10:554/live"
# s_id = "CAM-01"

# ==================================================

API_URL = "http://127.0.0.1:8000/api/v1/detections/"

# Load YOLO model
model = YOLO("yolov8n.pt")

# Open video source
cap = cv2.VideoCapture(source)

if not cap.isOpened():
    print("❌ Gagal membuka source video")
    exit()

# Ambil ukuran frame
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

line_y = h // 2

# Penyimpanan ID kendaraan
counter_ids = set()

print(f"🚦 Monitoring dimulai untuk sumber: {s_id}")

while cap.isOpened():

    success, frame = cap.read()

    if not success:
        print("✅ Stream selesai / terputus")
        break

    # YOLO Tracking
    results = model.track(
        frame,
        persist=True,
        classes=[2, 3, 5, 7],
        conf=0.4
    )

    # Cek object
    if results[0].boxes.id is not None:

        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        classes = results[0].boxes.cls.cpu().numpy().astype(int)

        for box, obj_id, cls_id in zip(boxes, ids, classes):

            x1, y1, x2, y2 = map(int, box)

            cy = int((y1 + y2) / 2)

            vehicle_type = model.names[cls_id]

            # Hitung kendaraan
            if (line_y - 10) < cy < (line_y + 10):

                if obj_id not in counter_ids:

                    counter_ids.add(obj_id)

                    total_count = len(counter_ids)

                    print(
                        f"✅ Kendaraan: {vehicle_type} | "
                        f"ID: {obj_id} | "
                        f"Total: {total_count}"
                    )

                    # Payload API
                    payload = {
                       "camera_id": s_id,  # Mengambil nilai "CAM-01" dari atas
                        "timestamp": datetime.now().isoformat(),
                        "vehicle_type": vehicle_type,
                        "count": total_count,
                        "direction": "inbound",
                        "confidence": float(confidence) if 'confidence' in locals() else 0.8
                    }

                    # Kirim ke backend
                    try:

                        response = requests.post(
                            API_URL,
                            json=payload,
                            allow_redirects=False
                        )

                        print(f"📡 API Status: {response.status_code}")

                    except Exception as e:

                        print(f"❌ Gagal kirim API: {e}")

# Release
cap.release()

print(f"🎯 Total kendaraan terhitung: {len(counter_ids)}")