"""
road_inference.py  v2
Layer 1 – Auto Road Detection + Adaptive Virtual Line

Perubahan v2:
- ROI otomatis menyesuaikan diri dari distribusi Y kendaraan yang terdeteksi
  (tidak lagi hardcode 35% dari atas — aman untuk semua sudut kamera)
- Confidence formula diperbaiki agar tidak stuck di 0%
"""

import logging
import numpy as np
from collections import deque
from typing import List, Dict

logger = logging.getLogger(__name__)


class RoadInference:
    def __init__(
        self,
        frame_width: int = 640,
        frame_height: int = 360,
        history_frames: int = 60,
        min_frames_ready: int = 10,
        roi_top_ratio: float = 0.35,   # masih dipakai sebagai fallback awal
    ):
        self.frame_width     = frame_width
        self.frame_height    = frame_height
        self.history_frames  = history_frames
        self.min_frames_ready = min_frames_ready

        # ROI adaptif — dimulai dari nilai default, lalu otomatis turun
        # berdasarkan di mana kendaraan sebenarnya terdeteksi
        self._roi_y_min_default = int(frame_height * roi_top_ratio)
        self.roi_y_min          = self._roi_y_min_default

        # Riwayat Y semua kendaraan (untuk kalibrasi ROI otomatis)
        self._all_cy_seen: deque = deque(maxlen=200)

        self._cx_history: deque     = deque(maxlen=history_frames)
        self._left_history: deque   = deque(maxlen=history_frames)
        self._right_history: deque  = deque(maxlen=history_frames)
        self._frames_with_vehicles  = 0

        self.road_x_min  = 0
        self.road_x_max  = frame_width
        self.centroid_x  = frame_width // 2
        self.confidence  = 0.0
        self.is_ready    = False

        logger.info(
            f"RoadInference init — frame={frame_width}x{frame_height} "
            f"history={history_frames} min_ready={min_frames_ready} "
            f"roi_top={roi_top_ratio:.0%} (adaptive)"
        )

    def update(self, bboxes: List[List[float]]) -> None:
        if not bboxes:
            return

        # Kumpulkan semua Y centroid dulu (sebelum filter ROI)
        # untuk kalibrasi ROI otomatis
        for b in bboxes:
            x1, y1, x2, y2 = b
            cy = (y1 + y2) / 2.0
            self._all_cy_seen.append(cy)

        # Kalibrasi ROI otomatis: setelah 20 sampel,
        # ROI disesuaikan ke persentil 10 dari semua Y yang terlihat
        # sehingga tidak ada kendaraan yang terbuang karena ROI terlalu ketat
        if len(self._all_cy_seen) >= 20:
            p10 = float(np.percentile(list(self._all_cy_seen), 10))
            # Ambil nilai lebih longgar antara default dan actual distribution
            self.roi_y_min = min(self._roi_y_min_default, max(0, int(p10 * 0.8)))

        # Filter dengan ROI yang sudah dikalibrasi
        valid_bboxes = [b for b in bboxes if self._in_roi(b)]
        if not valid_bboxes:
            return

        self._frames_with_vehicles += 1

        cx_list, x_min_list, x_max_list = [], [], []
        for bbox in valid_bboxes:
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cx_list.append(cx)
            x_min_list.append(float(x1))
            x_max_list.append(float(x2))

        self._cx_history.extend(cx_list)
        self._left_history.append(min(x_min_list))
        self._right_history.append(max(x_max_list))

        self._recalculate()

    def get_info(self) -> Dict:
        return {
            "is_ready":      self.is_ready,
            "confidence":    round(self.confidence, 3),
            "road_x_min":    self.road_x_min,
            "road_x_max":    self.road_x_max,
            "centroid_x":    self.centroid_x,
            "road_width_px": self.road_x_max - self.road_x_min,
            "frames_seen":   self._frames_with_vehicles,
            "cx_samples":    len(self._cx_history),
            "roi_y_min":     self.roi_y_min,
        }

    def classify_direction(self, bbox: List[float]) -> str:
        if not self.is_ready:
            return "Unknown"
        x1, _, x2, _ = bbox
        cx = (x1 + x2) / 2.0
        return "Inbound" if cx < self.centroid_x else "Outbound"

    def reset(self) -> None:
        self._cx_history.clear()
        self._left_history.clear()
        self._right_history.clear()
        self._all_cy_seen.clear()
        self._frames_with_vehicles = 0
        self.centroid_x = self.frame_width // 2
        self.road_x_min = 0
        self.road_x_max = self.frame_width
        self.confidence = 0.0
        self.is_ready   = False
        self.roi_y_min  = self._roi_y_min_default
        logger.info("RoadInference reset")

    def draw_overlay(self, frame, show_labels: bool = True):
        import cv2
        out = frame.copy()
        h, w = out.shape[:2]

        COLOR_LINE   = (0, 255, 255)
        COLOR_BOUND  = (0, 200, 100)
        COLOR_IN     = (255, 180, 0)
        COLOR_OUT    = (0, 100, 255)
        COLOR_INFO   = (220, 220, 220)

        if not self.is_ready:
            pct   = min(100, int(self._frames_with_vehicles / max(self.min_frames_ready, 1) * 100))
            bar_w = int(w * 0.4)
            bar_x = w // 2 - bar_w // 2
            cv2.rectangle(out, (bar_x, h - 36), (bar_x + bar_w, h - 18), (60, 60, 60), -1)
            cv2.rectangle(out, (bar_x, h - 36), (bar_x + int(bar_w * pct / 100), h - 18), (0, 220, 180), -1)
            cv2.putText(out, f"Mempelajari jalan... {pct}%",
                        (bar_x, h - 42), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_INFO, 1, cv2.LINE_AA)
            # Tampilkan ROI line agar user tahu area yang dipakai
            cv2.line(out, (0, self.roi_y_min), (w, self.roi_y_min), (80, 80, 80), 1)
            cv2.putText(out, f"ROI y={self.roi_y_min}px", (4, self.roi_y_min - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (80, 80, 80), 1)
            return out

        cv2.line(out, (self.road_x_min, self.roi_y_min), (self.road_x_min, h), COLOR_BOUND, 1)
        cv2.line(out, (self.road_x_max, self.roi_y_min), (self.road_x_max, h), COLOR_BOUND, 1)
        cv2.line(out, (self.centroid_x, self.roi_y_min), (self.centroid_x, h), COLOR_LINE, 2)

        if show_labels:
            mid_left  = (self.road_x_min + self.centroid_x) // 2
            mid_right = (self.centroid_x + self.road_x_max) // 2
            cv2.putText(out, "INBOUND",  (mid_left - 36,  self.roi_y_min + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_IN,  2, cv2.LINE_AA)
            cv2.putText(out, "OUTBOUND", (mid_right - 44, self.roi_y_min + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_OUT, 2, cv2.LINE_AA)

            conf_pct = int(self.confidence * 100)
            info_lines = [
                f"Road centroid : {self.centroid_x}px",
                f"Road width    : {self.road_x_max - self.road_x_min}px",
                f"Confidence    : {conf_pct}%",
                f"ROI y_min     : {self.roi_y_min}px (auto)",
            ]
            for i, line in enumerate(info_lines):
                cv2.putText(out, line, (w - 300, 24 + i * 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_INFO, 1, cv2.LINE_AA)
        return out

    def _in_roi(self, bbox: List[float]) -> bool:
        _, y1, _, y2 = bbox
        cy = (y1 + y2) / 2.0
        return cy >= self.roi_y_min

    def _recalculate(self) -> None:
        if len(self._cx_history) < 3:
            return

        cx_arr    = np.array(self._cx_history)
        left_arr  = np.array(self._left_history)  if self._left_history  else None
        right_arr = np.array(self._right_history) if self._right_history else None

        new_centroid = int(np.median(cx_arr))

        if left_arr is not None and len(left_arr) >= 2:
            new_left  = int(np.percentile(left_arr,  10))
            new_right = int(np.percentile(right_arr, 90))
        else:
            new_left  = int(np.percentile(cx_arr, 10))
            new_right = int(np.percentile(cx_arr, 90))

        new_left     = max(0, new_left)
        new_right    = min(self.frame_width, new_right)
        new_centroid = max(new_left + 10, min(new_right - 10, new_centroid))

        # Confidence: frame ratio + stabilitas std dev
        frames_ratio = min(1.0, self._frames_with_vehicles / self.min_frames_ready)
        std_dev      = float(np.std(cx_arr))
        stability    = max(0.0, 1.0 - (std_dev / (self.frame_width * 0.3)))
        new_confidence = round(frames_ratio * 0.6 + stability * 0.4, 3)

        self.road_x_min = new_left
        self.road_x_max = new_right
        self.centroid_x = new_centroid
        self.confidence = new_confidence
        self.is_ready   = (
            self._frames_with_vehicles >= self.min_frames_ready
            and new_confidence >= 0.4   # diturunkan dari 0.5
        )

        if self.is_ready and self._frames_with_vehicles == self.min_frames_ready:
            logger.info(
                f"Road READY — centroid={self.centroid_x}px "
                f"left={self.road_x_min} right={self.road_x_max} "
                f"conf={new_confidence:.1%} roi_y={self.roi_y_min}"
            )