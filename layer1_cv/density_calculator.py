"""
density_calculator.py
Layer 1 – Traffic Density Calculation
Implements DensityCalculator for per-camera aggregation and level classification.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


class DensityCalculator:
    """
    Calculate traffic density based on accumulated detections for a camera.

    One instance per camera. Counters reset after each interval.
    """

    def __init__(
        self,
        camera_id: str,
        road_capacity: int,
        interval_minutes: int = 15
    ):
        self.camera_id = camera_id
        self.road_capacity = road_capacity
        self.interval_minutes = interval_minutes

        self.vehicle_count: int = 0
        self.inflow_count: int = 0
        self.outflow_count: int = 0

        self.interval_start: datetime = datetime.now(timezone.utc)

        # Attempt to read thresholds from backend config; fallback if not available
        try:
            from layer2_backend import config
            self.low_threshold = config.DENSITY_LOW_THRESHOLD
            self.high_threshold = config.DENSITY_HIGH_THRESHOLD
        except Exception:
            # TODO: If config not available, these fallback values mirror Form 3
            self.low_threshold = 0.40
            self.high_threshold = 0.70
            logger.debug("Using fallback density thresholds: low=0.40, high=0.70")

    def aggregate(self, detections: List) -> None:
        """Aggregate detections into counters for the current interval."""
        if not detections:
            logger.debug("DensityCalculator.aggregate called with empty detections list")
            return

        for det in detections:
            try:
                # det is expected to be a Detection instance or dict-like
                is_valid = getattr(det, 'is_valid', None)
                if callable(is_valid):
                    valid = det.is_valid()
                else:
                    # fallback check
                    valid = (getattr(det, 'confidence', 0) is not None)
                if not valid:
                    continue

                self.vehicle_count += 1
                direction = getattr(det, 'direction_flow', None) or getattr(det, 'direction', None)
                if direction == 'Inbound':
                    self.inflow_count += 1
                elif direction == 'Outbound':
                    self.outflow_count += 1
                else:
                    # Unknown direction counts toward total but not inflow/outflow
                    pass
            except Exception:
                logger.exception("Error processing detection in aggregate")

    def compute_ratio(self) -> float:
        """Compute density_ratio = vehicle_count / road_capacity, clamped to [0.0,1.0]."""
        try:
            if self.road_capacity <= 0:
                logger.warning("road_capacity <= 0 in DensityCalculator.compute_ratio, returning 0.0")
                return 0.0
            ratio = float(self.vehicle_count) / float(self.road_capacity)
            if ratio < 0.0:
                ratio = 0.0
            if ratio > 1.0:
                ratio = 1.0
            return ratio
        except Exception:
            logger.exception("Error computing density ratio")
            return 0.0

    def classify_level(self) -> str:
        """Classify density level using thresholds (Low/Medium/High)."""
        ratio = self.compute_ratio()
        # Use thresholds from config if present
        low = getattr(self, 'low_threshold', 0.40)
        high = getattr(self, 'high_threshold', 0.70)
        if ratio < low:
            return "Low"
        if ratio <= high:
            return "Medium"
        return "High"

    def reset_counter(self) -> None:
        """Reset counters and set interval_start to now (UTC)."""
        self.vehicle_count = 0
        self.inflow_count = 0
        self.outflow_count = 0
        self.interval_start = datetime.now(timezone.utc)

    def get_interval_end(self) -> datetime:
        """Return interval end time = interval_start + interval_minutes."""
        return self.interval_start + timedelta(minutes=self.interval_minutes)

    def is_interval_elapsed(self) -> bool:
        """Return True if current UTC time >= interval_end."""
        now = datetime.now(timezone.utc)
        return now >= self.get_interval_end()

    def to_density_record(self) -> dict:
        """Return a dict ready to be saved to TRAFFIC_DENSITY table."""
        return {
            "camera_id": self.camera_id,
            "interval_start": self.interval_start,
            "interval_end": self.get_interval_end(),
            "total_vehicles": int(self.vehicle_count),
            "inflow_count": int(self.inflow_count),
            "outflow_count": int(self.outflow_count),
            "density_ratio": float(self.compute_ratio()),
            "density_level": self.classify_level()
        }
