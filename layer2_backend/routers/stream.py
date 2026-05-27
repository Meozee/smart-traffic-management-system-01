import cv2
import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ultralytics import YOLO
from datetime import datetime
from .. import models, database

router = APIRouter(prefix="/api/v1", tags=["Live Stream"])
model = YOLO("yolov8n.pt")

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

def generate_frames(camera_id: str, stream_url: str):
    cap = cv2.VideoCapture(stream_url)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    center_x = width // 2 
    
    # Melacak ID yang sudah tercatat agar tidak double count
    # Gunakan dict untuk menyimpan status terakhir agar bisa mendeteksi perubahan arah jika perlu
    tracked_ids = {}

    while True:
        success, frame = cap.read()
        if not success: break
        
        results = model.track(frame, persist=True, classes=[2, 3, 5, 7], conf=0.3)
        
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            clss = results[0].boxes.cls.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()

            for box, obj_id, cls_idx, conf in zip(boxes, ids, clss, confs):
                cx = int((box[0] + box[2]) / 2)
                
                # LOGIKA DIRECTION: Kiri = Inbound, Kanan = Outbound
                direction = "inbound" if cx < center_x else "outbound"
                
                # Catat ke DB hanya jika ID baru muncul atau belum pernah tercatat
                if obj_id not in tracked_ids:
                    tracked_ids[obj_id] = direction
                    
                    db = database.SessionLocal()
                    try:
                        new_detection = models.VehicleDetection(
                            camera_id=camera_id,
                            timestamp=datetime.now(),
                            vehicle_type=model.names[cls_idx],
                            count=1,
                            direction=direction, # Menyimpan arah ke DB
                            confidence=float(conf)
                        )
                        db.add(new_detection)
                        db.commit()
                        print(f"✅ [{direction.upper()}] {camera_id}: {model.names[cls_idx]} tercatat!")
                    except Exception as e:
                        db.rollback()
                    finally:
                        db.close()

        # Visualisasi
        visual_frame = results[0].plot()
        # Garis pembagi tengah
        cv2.line(visual_frame, (center_x, 0), (center_x, frame.shape[0]), (255, 255, 0), 2)
        
        # Penanda visual
        cv2.putText(visual_frame, "INBOUND (KIRI)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(visual_frame, "OUTBOUND (KANAN)", (center_x + 50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        ret, buffer = cv2.imencode(".jpg", visual_frame)
        if not ret: continue
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    cap.release()

@router.get("/stream/{camera_id}")
def video_feed(camera_id: str, db: Session = Depends(get_db)):
    camera = db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()
    if not camera: raise HTTPException(status_code=404, detail="Kamera tidak ditemukan")
    
    return StreamingResponse(
        generate_frames(camera.camera_id, camera.stream_url),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )