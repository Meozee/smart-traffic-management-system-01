import cv2
from ultralytics import YOLO

# 1. Load Model (Sesuai B.5 Component References)
model = YOLO('yolov8n.pt')

# 2. Buka Video (Implementasi UC-01)
video_path = "tests/sample_video1.mp4"
cap = cv2.VideoCapture(video_path)

# 3. Setup Video Writer (Untuk menyimpan hasil deteksi)
frame_width = int(cap.get(3))
frame_height = int(cap.get(4))
# Ambil FPS asli video, kalau gagal default ke 30
fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0: fps = 30

out = cv2.VideoWriter('tests/output_result.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))

print("Sedang memproses deteksi... Harap tunggu.")

while cap.isOpened():
    success, frame = cap.read()
    if success:
        # Jalankan Deteksi (Implementasi UC-03 & UC-04)
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        results = model(frame, classes=[2, 3, 5, 7], conf=0.5)
        
        # Gambar kotak deteksi (Bounding Box)
        annotated_frame = results[0].plot()
        
        # Simpan frame ke file output
        out.write(annotated_frame)
    else:
        # Jika video habis, keluar dari loop
        break

cap.release()
out.release()
print("Selesai! Cek hasilnya di folder tests/output_result.mp4")


def test_cv_module_basic():
    """Quick smoke test untuk memverifikasi cv_module.py berfungsi."""
    from cv_module import VideoCapture, VehicleDetector, Detection

    # Test VideoCapture
    cap = VideoCapture("traffic.mp4")
    opened = cap.open("traffic.mp4")
    print(f"[VideoCapture] open('traffic.mp4'): {opened}")

    if opened:
        frame = cap.read_frame()
        print(f"[VideoCapture] read_frame(): {'OK' if frame is not None else 'FAILED'}")

        if frame is not None:
            preprocessed = cap.preprocess(frame)
            if preprocessed is not None:
                print(f"[VideoCapture] preprocess(): shape={preprocessed.shape}, dtype={preprocessed.dtype}, "
                      f"min={preprocessed.min():.3f}, max={preprocessed.max():.3f}")
            else:
                print("[VideoCapture] preprocess(): FAILED (returned None)")

        cap.release()
        print("[VideoCapture] release(): OK")

    # Test VehicleDetector (hanya jika model ada)
    import os
    if os.path.exists("yolov8n.pt"):
        try:
            detector = VehicleDetector("yolov8n.pt", 0.5)
            print(f"[VehicleDetector] load_model(): device={detector.device}")

            if opened:
                cap2 = VideoCapture("traffic.mp4")
                cap2.open("traffic.mp4")
                frame2 = cap2.read_frame()
                prep2 = cap2.preprocess(frame2)
                detections = detector.detect(prep2)
                print(f"[VehicleDetector] detect(): {len(detections)} detections found")
                for det in detections[:3]:  # tampilkan max 3
                    print(f"  → {det.vehicle_type}, conf={det.confidence:.2f}, dir={det.direction_flow}")
                cap2.release()
        except Exception as e:
            print(f"[VehicleDetector] ERROR: {e}")
    else:
        print("[VehicleDetector] yolov8n.pt tidak ditemukan, skip test model.")

    print("\n✅ cv_module basic test selesai.")


if __name__ == "__main__":
    test_cv_module_basic()