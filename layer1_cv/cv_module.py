"""
cv_module.py
Layer 1 – Data Acquisition & Computer Vision
Implements Detection, VideoCapture, and VehicleDetector classes

Follows Form 3 Section B.6.1 class diagram and uses COCO IDs for vehicle mapping:
COCO: 2=car, 3=motorcycle, 5=bus, 7=truck

Note: Form 3 used a different custom mapping; this implementation uses COCO IDs
because `yolov8n.pt` is pretrained on COCO. Keep this documented here.

FIXED (v2):
- VideoCapture.__init__ sekarang langsung memanggil open() secara opsional
- open() tidak lagi menerima parameter duplikat; gunakan self.source
- CLASS_MAP dipindah ke VehicleDetector (Detection adalah pure DTO)
- _prev_centroids dibersihkan otomatis untuk track ID yang sudah tidak aktif
- load_model() raise RuntimeError jika semua upaya gagal
- Tambah _active_track_ids untuk cleanup centroid lama
- Tambah fallback tracker jika botsort.yaml tidak tersedia
- Perbaiki tipe hint yang kurang tepat
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, ClassVar, Set
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# COCO class mapping (didefinisikan di module level agar bisa dipakai bersama)
# ---------------------------------------------------------------------------
COCO_VEHICLE_MAP: Dict[int, str] = {
    2: "Car",
    3: "Motorcycle",
    5: "Bus",
    7: "Truck",
}


@dataclass
class Detection:
    """
    Represents a single detection result from YOLOv8.

    Pure data-transfer object (DTO): tidak menyimpan logic mapping class.
    CLASS_MAP dipindah ke VehicleDetector.
    """

    bbox: List[float]           # [x1, y1, x2, y2] dalam piksel
    confidence: float
    class_id: int
    vehicle_type: str
    direction_flow: str         # "Inbound" | "Outbound" | "Tracking" | "Unknown"
    timestamp: datetime

    def to_dict(self) -> dict:
        """Return attributes as a serializable dict (timestamp dalam format ISO UTC)."""
        return {
            "bbox": [float(x) for x in self.bbox],
            "confidence": float(self.confidence),
            "class_id": int(self.class_id),
            "vehicle_type": str(self.vehicle_type),
            "direction": str(self.direction_flow),
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
        }

    def is_valid(self, confidence_threshold: float = 0.5) -> bool:
        """Return True jika detection valid untuk perhitungan densitas."""
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
    """
    Wrapper around cv2.VideoCapture dengan preprocessing helpers.

    FIX: __init__ menerima `auto_open=True` agar caller tidak perlu
    memanggil open() secara manual (mengurangi risiko lupa).
    FIX: open() tidak lagi menerima parameter `source` — gunakan self.source
         agar tidak ada duplikasi/inkonsistensi state.
    """

    def __init__(self, source: str, auto_open: bool = True):
        self.source = source
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.fps: float = 0.0

        if auto_open:
            self.open()

    def open(self) -> bool:
        """
        Buka video source dan populate properti. Return True jika berhasil.

        FIX: Tidak lagi menerima parameter `source` terpisah — selalu
        menggunakan self.source sehingga state tetap konsisten.
        """
        try:
            # Tutup capture lama jika masih aktif
            if self.cap is not None:
                self.cap.release()

            self.cap = cv2.VideoCapture(self.source)
            if not self.cap or not self.cap.isOpened():
                logger.error(f"Unable to open video source: {self.source}")
                return False

            self.frame_width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)  or 0)
            self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            self.fps          = float(self.cap.get(cv2.CAP_PROP_FPS)        or 0.0)

            # Fallback defaults jika kamera tidak melaporkan properti
            if self.frame_width == 0 or self.frame_height == 0:
                self.frame_width, self.frame_height = 640, 640
            if self.fps == 0.0:
                self.fps = 30.0

            logger.info(
                f"Opened video source: {self.source} "
                f"({self.frame_width}x{self.frame_height}@{self.fps}fps)"
            )
            return True

        except Exception:
            logger.exception(f"Error opening source {self.source}")
            return False

    def read_frame(self) -> Optional[np.ndarray]:
        """Baca satu frame dari capture. Return frame BGR atau None."""
        if self.cap is None:
            logger.debug("VideoCapture.read_frame dipanggil tapi capture adalah None")
            return None
        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None
        return frame

    def preprocess(self, frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """
        Resize ke 640x640, normalisasi ke [0,1], konversi BGR→RGB, dtype float32.
        Return None jika frame tidak valid.
        """
        if frame is None:
            logger.warning("preprocess dipanggil dengan frame None")
            return None
        try:
            resized = cv2.resize(frame, (640, 640))
            rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            arr     = rgb.astype(np.float32) / 255.0
            return arr
        except Exception:
            logger.exception("Error preprocessing frame")
            return None

    def release(self) -> None:
        """Lepaskan resource cv2.VideoCapture."""
        try:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
        except Exception:
            logger.exception("Error releasing VideoCapture resource")

    # ------------------------------------------------------------------
    # Context manager support agar bisa dipakai dengan `with` statement
    # ------------------------------------------------------------------
    def __enter__(self) -> "VideoCapture":
        return self

    def __exit__(self, *_) -> None:
        self.release()


class VehicleDetector:
    """
    Wrapper untuk YOLOv8 vehicle detection dengan tracking.

    FIX: CLASS_MAP dipindah ke sini dari Detection (SRP).
    FIX: _prev_centroids dibersihkan setiap frame berdasarkan track ID aktif.
    FIX: load_model() raise RuntimeError jika semua upaya gagal.
    FIX: Fallback tracker jika botsort.yaml tidak tersedia.
    """

    VEHICLE_CLASS_IDS: ClassVar[List[int]] = [2, 3, 5, 7]

    # Mapping COCO class_id → nama kendaraan
    CLASS_MAP: ClassVar[Dict[int, str]] = COCO_VEHICLE_MAP

    # Nama tracker yang akan dicoba secara berurutan
    _TRACKER_FALLBACKS: ClassVar[List[str]] = ["botsort.yaml", "bytetrack.yaml"]

    def __init__(self, model_path: str, confidence_threshold: float = 0.5):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device: str = "cpu"
        self.model = None

        # track_id → sisi terakhir ("Sisi A" / "Sisi B")
        self._prev_centroids: Dict[int, str] = {}

        # Virtual line endpoints (default: garis vertikal di tengah 640x480)
        self.line_x1: int = 320
        self.line_y1: int = 0
        self.line_x2: int = 320
        self.line_y2: int = 480

        self.load_model()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Muat model YOLOv8 dengan ultralytics jika tersedia,
        fallback ke torch.jit jika ada.

        FIX: Raise RuntimeError jika semua upaya gagal, agar caller
        tidak berjalan diam-diam tanpa model yang valid.
        """
        # Attempt 1: ultralytics YOLO API
        try:
            from ultralytics import YOLO
            import torch

            self.model  = YOLO(self.model_path)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loaded YOLO model from '{self.model_path}' on device={self.device}")
            return
        except ImportError:
            logger.warning("ultralytics tidak tersedia, mencoba torch.jit...")
        except FileNotFoundError:
            raise FileNotFoundError(f"Model file tidak ditemukan: {self.model_path}")
        except Exception as e:
            logger.warning(f"ultralytics YOLO load gagal: {e}. Mencoba torch.jit...")

        # Attempt 2: TorchScript fallback
        try:
            import torch
            self.model  = torch.jit.load(self.model_path)
            self.device = "cpu"
            logger.info("Loaded TorchScript model (fallback)")
            return
        except FileNotFoundError:
            raise FileNotFoundError(f"Model file tidak ditemukan: {self.model_path}")
        except Exception as e:
            logger.exception(f"TorchScript load gagal: {e}")

        # FIX: Jangan biarkan model=None tanpa error — raise eksplisit
        raise RuntimeError(
            f"Gagal memuat model dari '{self.model_path}'. "
            "Pastikan ultralytics atau torch tersedia dan path model benar."
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def classify(self, class_id: int) -> str:
        """Map COCO class_id ke tipe kendaraan menggunakan CLASS_MAP."""
        return self.CLASS_MAP.get(class_id, "Unknown")

    def set_virtual_line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Set koordinat virtual line (2 endpoint untuk deteksi crossing)."""
        self.line_x1, self.line_y1 = x1, y1
        self.line_x2, self.line_y2 = x2, y2
        logger.info(f"Virtual line diset: ({x1},{y1}) → ({x2},{y2})")

    # ------------------------------------------------------------------
    # Direction logic
    # ------------------------------------------------------------------

    def get_direction(self, bbox: List[float], track_id: int) -> str:
        """
        Tentukan arah berdasarkan vektor D (metode cross product).
        Membagi frame menjadi dua sisi berdasarkan virtual line.

        Inbound  : Sisi A → Sisi B
        Outbound : Sisi B → Sisi A
        Tracking : Kendaraan baru atau belum menyeberangi garis
        """
        try:
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
        except (TypeError, ValueError):
            logger.warning(f"bbox tidak valid untuk track_id={track_id}: {bbox}")
            return "Unknown"

        # D = (Px - Lx1)(Ly2 - Ly1) - (Py - Ly1)(Lx2 - Lx1)
        D = (
            (cx - self.line_x1) * (self.line_y2 - self.line_y1)
            - (cy - self.line_y1) * (self.line_x2 - self.line_x1)
        )

        current_side = "Sisi A" if D > 0 else "Sisi B"
        prev_side    = self._prev_centroids.get(track_id)

        # Simpan posisi terkini
        self._prev_centroids[track_id] = current_side

        if prev_side is None:
            return "Tracking"  # Kendaraan baru, belum ada riwayat

        if prev_side != current_side:
            if prev_side == "Sisi A":
                return "Inbound"
            else:
                return "Outbound"

        return "Tracking"  # Bergerak tapi belum menyeberang

    def _cleanup_stale_tracks(self, active_ids: Set[int]) -> None:
        """
        FIX: Hapus track ID yang tidak aktif lagi dari _prev_centroids
        untuk mencegah memory leak pada sesi video yang panjang.
        """
        stale = set(self._prev_centroids) - active_ids
        for track_id in stale:
            del self._prev_centroids[track_id]
        if stale:
            logger.debug(f"Cleaned up {len(stale)} stale track(s): {stale}")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _try_track(self, frame: np.ndarray, tracker: str):
        """Jalankan model.track() dengan tracker tertentu. Return hasil atau None."""
        try:
            return self.model.track(
                frame,
                conf=self.confidence_threshold,
                persist=True,
                tracker=tracker,
            )
        except Exception as e:
            logger.warning(f"Tracker '{tracker}' gagal: {e}")
            return None

    def detect(self, frame: Optional[np.ndarray]) -> List[Detection]:
        """
        Jalankan YOLOv8 tracking pada frame dan return daftar Detection.
        Hanya mengembalikan deteksi di mana kendaraan SUDAH MENYEBERANGI
        virtual line (direction == "Inbound" atau "Outbound").

        FIX: Cleanup centroid lama setiap frame.
        FIX: Fallback tracker jika tracker utama tidak tersedia.
        """
        if frame is None:
            return []
        if self.model is None:
            logger.error("model adalah None — pastikan load_model() berhasil.")
            return []

        results: List[Detection] = []

        try:
            # Coba setiap tracker secara berurutan
            res = None
            for tracker_name in self._TRACKER_FALLBACKS:
                res = self._try_track(frame, tracker_name)
                if res is not None:
                    break

            if res is None:
                logger.error("Semua tracker gagal dijalankan.")
                return results

            boxes = getattr(res[0], "boxes", None)
            if boxes is None or boxes.id is None:
                # Tidak ada track aktif pada frame ini → bersihkan semua centroid
                self._cleanup_stale_tracks(set())
                return results

            xyxy      = boxes.xyxy.cpu().numpy()
            confs     = boxes.conf.cpu().numpy()
            cls       = boxes.cls.cpu().numpy()
            track_ids = boxes.id.cpu().numpy().astype(int)

            # Kumpulkan ID aktif untuk cleanup setelah loop
            active_ids: Set[int] = set(track_ids)

            for i in range(len(boxes)):
                class_id = int(cls[i])

                # Filter: hanya kelas kendaraan yang relevan
                if class_id not in self.VEHICLE_CLASS_IDS:
                    continue

                confidence = float(confs[i])

                # Filter: confidence rendah diabaikan
                if confidence < self.confidence_threshold:
                    continue

                track_id     = int(track_ids[i])
                vehicle_type = self.classify(class_id)
                direction    = self.get_direction(xyxy[i].tolist(), track_id)

                # Hanya catat kendaraan yang benar-benar menyeberang garis
                if direction in ("Inbound", "Outbound"):
                    results.append(
                        Detection(
                            bbox=xyxy[i].tolist(),
                            confidence=confidence,
                            class_id=class_id,
                            vehicle_type=vehicle_type,
                            direction_flow=direction,
                            timestamp=datetime.now(timezone.utc),
                        )
                    )

            # FIX: Bersihkan track ID yang sudah tidak aktif
            self._cleanup_stale_tracks(active_ids)

        except Exception:
            logger.exception("Error selama tracking")

        return results