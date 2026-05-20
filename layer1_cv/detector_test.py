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