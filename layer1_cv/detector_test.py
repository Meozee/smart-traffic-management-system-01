import cv2
from ultralytics import YOLO
import requests
from datetime import datetime
import subprocess

API = "http://localhost:8000/api/v1"
CAMERA_IDS = ["CAM-001", "CAM-002", "CAM-003", "CAM-004"]

model = YOLO('yolov8n.pt')
CLASS_MAP = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}

for idx, CAMERA_ID in enumerate(CAMERA_IDS):
    print(f"\nMemproses {CAMERA_ID}...")
    video_path = "tests/sample_video1.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(3))
    h = int(cap.get(4))

    out = cv2.VideoWriter(f'tests/output_{CAMERA_ID}.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
    frame_count = 0

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
        results = model(frame, classes=[2, 3, 5, 7], conf=0.5)
        annotated_frame = results[0].plot()
        out.write(annotated_frame)

        if frame_count % 10 == 0:
            boxes = results[0].boxes
            if boxes is not None and len(boxes) > 0:
                counts = {}
                for box in boxes:
                    cls = int(box.cls[0])
                    vtype = CLASS_MAP.get(cls, 'unknown')
                    conf = float(box.conf[0])
                    counts[vtype] = counts.get(vtype, {'count': 0, 'conf': []})
                    counts[vtype]['count'] += 1
                    counts[vtype]['conf'].append(conf)
                for vtype, data in counts.items():
                    avg_conf = sum(data['conf']) / len(data['conf'])
                    payload = {
                        "camera_id": CAMERA_ID,
                        "timestamp": datetime.utcnow().isoformat(),
                        "vehicle_type": vtype,
                        "count": data['count'],
                        "direction": "inbound",
                        "bbox_data": {},
                        "confidence": round(avg_conf, 2)
                    }
                    try:
                        requests.post(f"{API}/detections/", json=payload, timeout=2)
                        print(f"[{CAMERA_ID}] Posted: {vtype} x{data['count']}")
                    except Exception as e:
                        print(f"ERROR: {e}")
        frame_count += 1

    cap.release()
    out.release()

    # Convert ke format browser-compatible
    print(f"Converting {CAMERA_ID}...")
    subprocess.run([
        'ffmpeg', '-y', '-stream_loop', '9',
        '-i', f'tests/output_{CAMERA_ID}.mp4',
        '-c:v', 'libx264', '-preset', 'fast',
        f'../layer3_dashboard/cam{idx+1}_loop.mp4'
    ])
    print(f"{CAMERA_ID} done!")

print("\nSelesai semua kamera!")