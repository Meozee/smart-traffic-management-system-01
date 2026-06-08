"""
cv_module.py
Layer 1 – Data Acquisition & Computer Vision
Implements Detection, VideoCapture, and VehicleDetector classes

Follows Form 3 Section B.6.1 class diagram and uses COCO IDs for vehicle mapping:
COCO: 2=car, 3=motorcycle, 5=bus, 7=truck

Note: Form 3 used a different custom mapping; this implementation uses COCO IDs
because `yolov8n.pt` is pretrained on COCO. Keep this documented here.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple, ClassVar
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Represents a single detection result from YOLOv8."""

    bbox: List[float]
    confidence: float
    class_id: int
    vehicle_type: str
    direction_flow: str
    timestamp: datetime

    # COCO mapping used by this system
    CLASS_MAP: ClassVar[Dict[int, str]] = {
        2: "Car",
        3: "Motorcycle",
        5: "Bus",
        7: "Truck"
    }

    def to_dict(self) -> dict:
        """Return attributes as a serializable dict (timestamp in ISO format)."""
        return {
            "bbox": [float(x) for x in self.bbox],
            "confidence": float(self.confidence),
            "class_id": int(self.class_id),
            "vehicle_type": str(self.vehicle_type),
            "direction": str(self.direction_flow),
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat()
        }

    def is_valid(self, confidence_threshold: float = 0.5) -> bool:
        """Return True if detection is valid for density calculation."""
        if self.confidence is None:
            return False
        if self.confidence < confidence_threshold:
            return False
        if not self.vehicle_type or self.vehicle_type == "Unknown":
            return False
        if not self.bbox or len(self.bbox) != 4:
            return False
        return True


class VideoCapture:
    """Wrapper around cv2.VideoCapture with preprocessing helpers."""

    def __init__(self, source: str):
        self.source = source
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.fps: float = 0.0

    def open(self, source: str) -> bool:
        """Open video source and populate properties. Returns True on success."""
        try:
            self.cap = cv2.VideoCapture(source)
            if not self.cap or not self.cap.isOpened():
                logger.error(f"Unable to open video source: {source}")
                return False
            self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
            # Fallback defaults
            if self.frame_width == 0 or self.frame_height == 0:
                self.frame_width, self.frame_height = 640, 640
            if self.fps == 0.0:
                self.fps = 30.0
            logger.info(f"Opened video source: {source} ({self.frame_width}x{self.frame_height}@{self.fps}fps)")
            return True
        except Exception as e:
            logger.exception(f"Error opening source {source}: {e}")
            return False

    def read_frame(self) -> Optional[np.ndarray]:
        """Read one frame from the capture. Returns BGR frame or None."""
        if self.cap is None:
            logger.debug("VideoCapture.read_frame called but capture is None")
            return None
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None
        return frame

    def preprocess(self, frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """Resize to 640x640, normalize to [0,1], convert BGR->RGB, dtype float32."""
        if frame is None:
            logger.warning("preprocess called with None frame")
            return None
        try:
            resized = cv2.resize(frame, (640, 640))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            arr = rgb.astype(np.float32) / 255.0
            return arr
        except Exception as e:
            logger.exception(f"Error preprocessing frame: {e}")
            return None

    def release(self) -> None:
        """Release the underlying cv2.VideoCapture resource."""
        try:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
        except Exception:
            logger.exception("Error releasing VideoCapture resource")


class VehicleDetector:
    """Wrapper for YOLOv8 vehicle detection logic."""

    VEHICLE_CLASS_IDS = [2, 3, 5, 7]

    def __init__(self, model_path: str, confidence_threshold: float = 0.5):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device: str = "cpu"
        self.model = None
        self._prev_centroids: Dict[int, Tuple[float, float]] = {}
        self.virtual_line_x: int = 320
        self.load_model()

    def load_model(self) -> None:
        """Load YOLOv8 model using ultralytics if available, fallback
        to torch.jit if present. Raises FileNotFoundError if model missing."""
        try:
            # Prefer ultralytics YOLO API
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            # Determine device
            import torch
            if torch.cuda.is_available():
                self.device = 'cuda'
            else:
                self.device = 'cpu'
            logger.info(f"Loaded YOLO model on device={self.device}")
        except Exception as e:
            logger.warning(f"ultralytics YOLO load failed: {e}. Trying torch.jit load...")
            try:
                import torch
                self.model = torch.jit.load(self.model_path)
                self.device = 'cpu'
                logger.info("Loaded TorchScript model (fallback)")
            except FileNotFoundError:
                logger.exception(f"Model file not found: {self.model_path}")
                raise FileNotFoundError(f"Model file not found: {self.model_path}")
            except Exception as e2:
                logger.exception(f"Failed to load model: {e2}")
                self.model = None

    def detect(self, frame: Optional[np.ndarray]) -> List[Detection]:
        """Run inference on a preprocessed frame and return list of Detection."""
        results: List[Detection] = []
        if frame is None:
            return results
        if self.model is None:
            logger.debug("No model loaded, skipping detection")
            return results

        try:
            # If using ultralytics YOLO
            if hasattr(self.model, 'predict') or hasattr(self.model, '__call__'):
                # ultralytics model accepts numpy array in HWC with RGB values 0-1 or 0-255
                # pass frame as-is (float32 0-1)
                res = None
                try:
                    res = self.model(frame, conf=self.confidence_threshold)
                except TypeError:
                    # Some ultralytics versions expect predict()
                    res = self.model.predict(frame, conf=self.confidence_threshold)

                # res can be a Results object or list-like
                r0 = res[0]
                boxes = getattr(r0, 'boxes', None)
                if boxes is None:
                    return results
                xyxy = getattr(boxes, 'xyxy', None)
                confs = getattr(boxes, 'conf', None)
                cls = getattr(boxes, 'cls', None)

                # iterate
                for i in range(len(boxes)):
                    try:
                        x1, y1, x2, y2 = map(float, xyxy[i])
                        conf = float(confs[i]) if confs is not None else 0.0
                        class_id = int(cls[i].item()) if hasattr(cls[i], 'item') else int(cls[i])
                    except Exception:
                        continue

                    if class_id not in self.VEHICLE_CLASS_IDS:
                        continue
                    if conf < self.confidence_threshold:
                        continue

                    vehicle_type = self.classify(class_id)
                    # No tracker id provided in this layer; direction unknown by default
                    direction = "Unknown"
                    det = Detection(
                        bbox=[x1, y1, x2, y2],
                        confidence=conf,
                        class_id=class_id,
                        vehicle_type=vehicle_type,
                        direction_flow=direction,
                        timestamp=datetime.now(timezone.utc)
                    )
                    results.append(det)
            else:
                logger.debug("Model object doesn't support predict/call - skipping")
        except Exception as e:
            logger.exception(f"Error during detection: {e}")

        return results

    def classify(self, class_id: int) -> str:
        """Map COCO class_id to vehicle type using Detection.CLASS_MAP."""
        return Detection.CLASS_MAP.get(class_id, "Unknown")

    def get_direction(self, bbox: List[float], track_id: Optional[int] = None) -> str:
        """Determine direction based on centroid movement across virtual_line_x."""
        try:
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
        except Exception:
            return "Unknown"

        if track_id is None:
            return "Unknown"

        prev = self._prev_centroids.get(track_id)
        if prev is None:
            self._prev_centroids[track_id] = (cx, cy)
            return "Unknown"

        prev_cx, prev_cy = prev
        # stationary threshold
        if abs(cx - prev_cx) < 5:
            direction = "Unknown"
        else:
            if prev_cx < self.virtual_line_x <= cx:
                direction = "Inbound"
            elif prev_cx >= self.virtual_line_x > cx:
                direction = "Outbound"
            else:
                direction = "Unknown"

        # update centroid
        self._prev_centroids[track_id] = (cx, cy)
        return direction

    def set_virtual_line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Menyimpan 4 titik koordinat untuk garis fleksibel."""
        self.line_x1 = x1
        self.line_y1 = y1
        self.line_x2 = x2
        self.line_y2 = y2
        logger.info(f"Garis Virtual Diatur: ({x1},{y1}) ke ({x2},{y2})")

    def detect(self, frame: Optional[np.ndarray]) -> List[Detection]:
        results: List[Detection] = []
        if frame is None or self.model is None:
            return results

        try:
            # 1. UBAH KE MODE TRACKING! (persist=True wajib agar mobil punya ID)
            res = self.model.track(frame, conf=self.confidence_threshold, persist=True, tracker="botsort.yaml")
            
            boxes = getattr(res[0], 'boxes', None)
            if boxes is None or boxes.id is None: # Jika tidak ada yang terlacak
                return results

            xyxy = boxes.xyxy.cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            cls = boxes.cls.cpu().numpy()
            track_ids = boxes.id.cpu().numpy().astype(int) # Ambil ID Pelacakan

            for i in range(len(boxes)):
                class_id = int(cls[i])
                if class_id not in self.VEHICLE_CLASS_IDS:
                    continue
                
                track_id = track_ids[i]
                vehicle_type = self.classify(class_id)
                
                # 2. Hitung arah berdasarkan pergerakan centroid terhadap 4 titik garis
                direction = self.get_direction(xyxy[i], track_id)

                # 3. Hanya catat jika statusnya jelas menyeberang (Inbound/Outbound)
                if direction in ["Inbound", "Outbound"]:
                    det = Detection(
                        bbox=xyxy[i].tolist(),
                        confidence=float(confs[i]),
                        class_id=class_id,
                        vehicle_type=vehicle_type,
                        direction_flow=direction,
                        timestamp=datetime.now(timezone.utc)
                    )
                    results.append(det)

        except Exception as e:
            logger.exception(f"Error tracking: {e}")

        return results

    def get_direction(self, bbox: List[float], track_id: int) -> str:
        """Menghitung arah menggunakan pemisah ruang Vektor D (2 titik garis)."""
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        # Rumus Vektor D: Membagi layar menjadi dua sisi (Positif dan Negatif)
        D = (cx - self.line_x1) * (self.line_y2 - self.line_y1) - (cy - self.line_y1) * (self.line_x2 - self.line_x1)
        current_side = "Sisi A" if D > 0 else "Sisi B"

        prev_side = self._prev_centroids.get(track_id)
        
        # Simpan posisi terbaru
        self._prev_centroids[track_id] = current_side

        if prev_side is None:
            return "Tracking" # Mobil baru masuk frame, belum menyeberang

        # Jika sisi sebelumnya berbeda dengan sisi sekarang = MENYEBERANG!
        if prev_side != current_side:
            if prev_side == "Sisi A" and current_side == "Sisi B":
                return "Inbound"
            elif prev_side == "Sisi B" and current_side == "Sisi A":
                return "Outbound"

        return "Tracking" # Sedang bergerak tapi belum lewat garis