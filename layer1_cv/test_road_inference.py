"""
test_road_inference.py  v3
- Counting kumulatif yang stabil
- Arah berdasarkan pergerakan Y: menjauh dari kamera (Y turun) = Inbound,
  mendekat ke kamera (Y naik) = Outbound
- Virtual line tidak dipakai untuk crossing — hanya sebagai visualisasi
- TRACK_DIST_THRESHOLD otomatis menyesuaikan resolusi video
- Road learning dipercepat: is_ready tidak ditunggu untuk mulai counting

Tekan Q/ESC = keluar | R = reset counter
"""

import cv2
import sys
import time
import argparse
import logging
import numpy as np
from collections import defaultdict
from road_inference import RoadInference

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_road")

CLR_INBOUND  = (255, 160,  30)
CLR_OUTBOUND = (50,  80,  255)
CLR_UNKNOWN  = (150, 150, 150)
CLR_TEXT     = (230, 230, 230)
CLR_PANEL    = (20,  20,  20)
FONT         = cv2.FONT_HERSHEY_SIMPLEX

# Minimum perpindahan Y (piksel) untuk dianggap bergerak
# Di-scale otomatis terhadap tinggi frame
MIN_Y_MOVEMENT_RATIO = 0.015   # 1.5% dari tinggi frame


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video",     default="traffic.mp4")
    p.add_argument("--model",     default="yolov8n.pt")
    p.add_argument("--conf",      type=float, default=0.35)
    p.add_argument("--history",   type=int,   default=60)
    p.add_argument("--min-ready", type=int,   default=10)
    return p.parse_args()


def load_yolo(model_path, conf):
    try:
        from ultralytics import YOLO
        model = YOLO(model_path)
        logger.info(f"Model loaded: {model_path}")
        return model
    except Exception as e:
        logger.error(f"Gagal load model: {e}")
        return None


def detect_vehicles(model, frame_rgb, conf):
    VEHICLE_IDS = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}
    results = []
    if model is None:
        return results
    try:
        res   = model(frame_rgb, conf=conf, verbose=False)
        boxes = res[0].boxes
        if boxes is None:
            return results
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if cls_id not in VEHICLE_IDS:
                continue
            x1, y1, x2, y2 = map(float, boxes.xyxy[i])
            cf = float(boxes.conf[i].item())
            results.append(([x1, y1, x2, y2], cls_id, cf, VEHICLE_IDS[cls_id]))
    except Exception as e:
        logger.debug(f"Detection error: {e}")
    return results


class DirectionTracker:
    """
    Tracker kendaraan berbasis pergerakan sumbu Y.

    Logika arah:
        - Kendaraan bergerak ke Y lebih besar (turun di frame) = MENJAUH dari kamera = Inbound
        - Kendaraan bergerak ke Y lebih kecil (naik di frame)  = MENDEKAT ke kamera  = Outbound

    Alasan ini lebih reliable:
        - Tidak bergantung pada virtual line yang masih belajar
        - Tidak terpengaruh posisi horizontal kendaraan
        - Bekerja untuk semua orientasi jalan selama kamera elevated
    """

    def __init__(self, frame_width, frame_height,
                 max_age=12, history_len=6):
        self.frame_width  = frame_width
        self.frame_height = frame_height
        self.max_age      = max_age
        self.history_len  = history_len

        # Threshold jarak matching — scale otomatis ke resolusi
        self.match_dist   = frame_width * 0.12

        # Threshold Y movement — scale ke tinggi frame
        self.min_y_move   = frame_height * MIN_Y_MOVEMENT_RATIO

        self.tracks   = {}    # id → {cx, cy, age, y_history, label, counted, direction}
        self.next_id  = 0

        # Statistik kumulatif
        self.total_vehicles = 0
        self.inbound_count  = 0
        self.outbound_count = 0
        self.type_counts    = defaultdict(int)

    def update(self, detections):
        """
        detections: list of ([x1,y1,x2,y2], cls_id, conf, label)
        Return: dict track_id → direction string (untuk warna bbox)
        """
        det_data = []
        for (bbox, cls_id, conf, label) in detections:
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            det_data.append((cx, cy, bbox, label))

        matched_tracks = set()
        matched_dets   = set()

        # Match deteksi ke track existing
        for tid, track in self.tracks.items():
            best_dist = self.match_dist
            best_di   = None
            for di, (cx, cy, bbox, label) in enumerate(det_data):
                if di in matched_dets:
                    continue
                dist = ((cx - track['cx'])**2 + (cy - track['cy'])**2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_di   = di
            if best_di is not None:
                matched_tracks.add(tid)
                matched_dets.add(best_di)
                cx, cy, bbox, label = det_data[best_di]

                # Simpan riwayat Y
                track['y_history'].append(cy)
                if len(track['y_history']) > self.history_len:
                    track['y_history'].pop(0)

                track['cx']  = cx
                track['cy']  = cy
                track['age'] = 0

                # Tentukan arah dari trend Y history
                direction = self._calc_direction(track['y_history'])
                track['direction'] = direction

                # Hitung hanya sekali saat arah sudah jelas dan belum dihitung
                if not track['counted'] and direction != 'Unknown':
                    track['counted'] = True
                    self.total_vehicles += 1
                    self.type_counts[label] += 1
                    if direction == 'Inbound':
                        self.inbound_count += 1
                    else:
                        self.outbound_count += 1

        # Track baru untuk deteksi yang tidak match
        for di, (cx, cy, bbox, label) in enumerate(det_data):
            if di in matched_dets:
                continue
            self.tracks[self.next_id] = {
                'cx': cx, 'cy': cy, 'age': 0,
                'y_history': [cy],
                'label': label, 'counted': False, 'direction': 'Unknown'
            }
            self.next_id += 1

        # Hapus track tua
        dead = [tid for tid, t in self.tracks.items() if t['age'] >= self.max_age]
        for tid in dead:
            del self.tracks[tid]

        # Tambah usia track yang tidak di-match
        for tid in self.tracks:
            if tid not in matched_tracks:
                self.tracks[tid]['age'] += 1

        # Buat mapping bbox centroid → direction untuk rendering
        dir_map = {}
        for di, (cx, cy, bbox, label) in enumerate(det_data):
            best_tid = None
            best_d   = self.match_dist
            for tid, track in self.tracks.items():
                d = ((cx - track['cx'])**2 + (cy - track['cy'])**2) ** 0.5
                if d < best_d:
                    best_d   = d
                    best_tid = tid
            if best_tid is not None:
                dir_map[di] = self.tracks[best_tid]['direction']
            else:
                dir_map[di] = 'Unknown'
        return dir_map

    def _calc_direction(self, y_history):
        """
        Hitung arah dari riwayat Y.
        Y bertambah (naik angka) = turun di layar = menjauh = Inbound
        Y berkurang             = naik di layar   = mendekat = Outbound
        """
        if len(y_history) < 3:
            return 'Unknown'
        # Regresi linear sederhana pada Y history
        n  = len(y_history)
        xs = list(range(n))
        x_mean = (n - 1) / 2.0
        y_mean = sum(y_history) / n
        num = sum((xs[i] - x_mean) * (y_history[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        if den == 0:
            return 'Unknown'
        slope = num / den   # piksel per frame

        if slope > self.min_y_move:
            return 'Inbound'    # Y naik = menjauh dari kamera
        elif slope < -self.min_y_move:
            return 'Outbound'   # Y turun = mendekat ke kamera
        return 'Unknown'

    def reset_counts(self):
        self.total_vehicles = 0
        self.inbound_count  = 0
        self.outbound_count = 0
        self.type_counts.clear()
        for t in self.tracks.values():
            t['counted'] = False
        logger.info("Counter di-reset.")


def draw_bbox(frame, bbox, label, direction, conf):
    x1, y1, x2, y2 = map(int, bbox)
    color = CLR_INBOUND if direction == "Inbound" else \
            CLR_OUTBOUND if direction == "Outbound" else CLR_UNKNOWN
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{label} {conf:.2f}"
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.44, 1)
    by = max(y1 - 4, th + 4)
    cv2.rectangle(frame, (x1, by - th - 4), (x1 + tw + 4, by + 2), color, -1)
    cv2.putText(frame, text, (x1 + 2, by - 2), FONT, 0.44, (10, 10, 10), 1, cv2.LINE_AA)
    arrow = "v IN" if direction == "Inbound" else "^ OUT" if direction == "Outbound" else "?"
    cv2.putText(frame, arrow, (x1 + 2, y2 - 5), FONT, 0.38, color, 1, cv2.LINE_AA)


def draw_stats_panel(frame, tracker, ri_info, fps, frame_no):
    panel_w, panel_h = 235, 215
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), CLR_PANEL, -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    conf_pct = int(ri_info.get('confidence', 0) * 100)
    ready    = ri_info.get('is_ready', False)
    road_status = f"{conf_pct}% READY" if ready else f"{conf_pct}% learning..."
    road_color  = (0, 220, 140) if ready else (180, 180, 50)

    lines = [
        (f"FPS        : {fps:.1f}",                                  CLR_TEXT),
        (f"Frame      : {frame_no}",                                  CLR_TEXT),
        (f"Road       : {road_status}",                               road_color),
        (f"Centroid   : {ri_info.get('centroid_x', 0)}px",            CLR_TEXT),
        ("──── Kumulatif ────",                                        (100, 220, 180)),
        (f"Car        : {tracker.type_counts.get('Car', 0)}",         CLR_TEXT),
        (f"Motorcycle : {tracker.type_counts.get('Motorcycle', 0)}",  CLR_TEXT),
        (f"Bus        : {tracker.type_counts.get('Bus', 0)}",         CLR_TEXT),
        (f"Truck      : {tracker.type_counts.get('Truck', 0)}",       CLR_TEXT),
        (f"Total      : {tracker.total_vehicles}",                    (255, 255, 100)),
        ("──── Arah (Y) ────",                                         (100, 220, 180)),
        (f"Inbound  v : {tracker.inbound_count}",                     CLR_INBOUND),
        (f"Outbound ^ : {tracker.outbound_count}",                    CLR_OUTBOUND),
        ("[ R ] Reset counter",                                        (100, 100, 100)),
    ]
    for i, (text, color) in enumerate(lines):
        cv2.putText(frame, text, (8, 17 + i * 15), FONT, 0.37, color, 1, cv2.LINE_AA)


def main():
    args = parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        logger.error(f"Tidak bisa membuka video: {args.video}")
        sys.exit(1)

    fw      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"Video: {args.video} | {fw}x{fh} @ {fps_src:.1f}fps | {total} frames")
    logger.info(f"Match dist: {fw * 0.12:.0f}px | Min Y move: {fh * MIN_Y_MOVEMENT_RATIO:.1f}px")

    model   = load_yolo(args.model, args.conf)
    ri      = RoadInference(fw, fh, args.history, args.min_ready)
    tracker = DirectionTracker(fw, fh)

    frame_no = 0
    fps_calc = fps_src
    t_prev   = time.time()

    cv2.namedWindow("STMS – Road Inference Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("STMS – Road Inference Test", min(fw, 1280), min(fh, 720))
    logger.info("Mulai. Q/ESC = keluar | R = reset counter")

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ri.reset()
            logger.info("Video selesai — mengulang.")
            continue

        frame_no += 1
        t_now    = time.time()
        fps_calc = 0.9 * fps_calc + 0.1 * (1.0 / max(t_now - t_prev, 1e-6))
        t_prev   = t_now

        frame_rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        detections = detect_vehicles(model, frame_rgb, args.conf)

        ri.update([d[0] for d in detections])
        ri_info = ri.get_info()

        dir_map = tracker.update(detections)

        for di, (bbox, cls_id, conf_val, label) in enumerate(detections):
            direction = dir_map.get(di, 'Unknown')
            draw_bbox(frame, bbox, label, direction, conf_val)

        frame = ri.draw_overlay(frame, show_labels=True)
        draw_stats_panel(frame, tracker, ri_info, fps_calc, frame_no)

        cv2.imshow("STMS – Road Inference Test", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break
        elif key in (ord('r'), ord('R')):
            tracker.reset_counts()

    cap.release()
    cv2.destroyAllWindows()

    logger.info("=" * 50)
    logger.info(f"TOTAL KENDARAAN  : {tracker.total_vehicles}")
    logger.info(f"INBOUND   (jauh) : {tracker.inbound_count}")
    logger.info(f"OUTBOUND (dekat) : {tracker.outbound_count}")
    for k, v in tracker.type_counts.items():
        logger.info(f"  {k:12s}   : {v}")
    info = ri.get_info()
    logger.info(f"ROAD CONFIDENCE  : {info['confidence']:.1%}")
    logger.info(f"ROAD CENTROID    : {info['centroid_x']}px")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()