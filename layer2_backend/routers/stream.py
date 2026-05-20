import cv2
import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ultralytics import YOLO
from datetime import datetime
from zoneinfo import ZoneInfo
from .. import models, database

router = APIRouter(prefix="/api/v1", tags=["Live Stream"])

# Load model secara global
model = YOLO("yolov8n.pt")

# Timezone WIB
WIB = ZoneInfo("Asia/Jakarta")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FITUR BARU: Menambahkan parameter virtual_line_y ---
def generate_frames(camera_id: str, stream_url: str, virtual_line_y: int):
    cap = cv2.VideoCapture(stream_url)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
    
    already_counted = set()
    frame_count = 0 

    while True:
        success, frame = cap.read()
        if not success: break

        frame_count += 1
        h, w, _ = frame.shape
        
        if frame_count % 3 == 0:
            results = model.track(frame, persist=True, classes=[2, 3, 5, 7], conf=0.3)
            
            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                ids = results[0].boxes.id.cpu().numpy().astype(int)
                clss = results[0].boxes.cls.cpu().numpy().astype(int)
                confs = results[0].boxes.conf.cpu().numpy()

                for box, obj_id, cls_idx, conf in zip(boxes, ids, clss, confs):
                    cy = int((box[1] + box[3]) / 2)
                    
                    # Logika Garis Virtual menggunakan nilai dari Database
                    if (virtual_line_y - 20) < cy < (virtual_line_y + 20):
                        if obj_id not in already_counted:
                            already_counted.add(obj_id)
                            
                            label_name = model.names[cls_idx]
                            
                            db = database.SessionLocal()
                            try:
                                new_detection = models.VehicleDetection(
                                    camera_id=camera_id,
                                    timestamp=datetime.now(),
                                    vehicle_type=label_name, 
                                    count=1,
                                    direction="inbound",
                                    confidence=float(conf)
                                )
                                db.add(new_detection)
                                db.commit()
                                print(f"✅ [KLASIFIKASI] {camera_id}: {label_name} #{obj_id} tercatat!")
                            except Exception as e:
                                db.rollback()
                                print(f"❌ Error DB: {e}")
                            finally:
                                db.close()

            visual_frame = results[0].plot()
        else:
            visual_frame = frame

        # Gambar Garis Kuning sesuai posisi spesifik kamera ini
        cv2.line(visual_frame, (0, virtual_line_y), (w, virtual_line_y), (0, 255, 255), 2) 
        cv2.putText(visual_frame, f"Sesi Ini: {len(already_counted)}", (10, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ret, buffer = cv2.imencode(".jpg", visual_frame)
        if not ret: continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    cap.release()

@router.get("/stream/{camera_id}")
def video_feed(camera_id: str, db: Session = Depends(get_db)):
    camera = db.query(models.Camera).filter(
        models.Camera.camera_id == camera_id
    ).first()

    if not camera:
        raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")

    # --- FITUR BARU: Kirimkan nilai virtual_line_y dari database ke generator YOLO ---
    return StreamingResponse(
        generate_frames(camera.camera_id, camera.stream_url, camera.virtual_line_y),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )