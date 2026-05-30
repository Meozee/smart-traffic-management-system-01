"""
Test suite for DensityCalculator class.
Covers test cases T-07-01, T-07-02, T-07-03 dari Form 3 Section D.2
"""
import pytest
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from layer1_cv.density_calculator import DensityCalculator
from layer1_cv.cv_module import Detection


def make_detection(direction: str = "Inbound", confidence: float = 0.8) -> Detection:
    """Helper: buat Detection dummy untuk testing."""
    return Detection(
        bbox=[10.0, 20.0, 100.0, 200.0],
        confidence=confidence,
        class_id=2,
        vehicle_type="Car",
        direction_flow=direction,
        timestamp=datetime.now(timezone.utc)
    )


class TestDensityCalculatorClassifyLevel:
    """T-07-01, T-07-02, T-07-03: Test klasifikasi level density."""

    def test_density_low_when_below_40_percent(self):
        """T-07-01: 20 kendaraan dari kapasitas 100 = 20% → Low."""
        calc = DensityCalculator(camera_id="CAM-001", road_capacity=100)
        detections = [make_detection() for _ in range(20)]
        calc.aggregate(detections)

        assert calc.classify_level() == "Low"
        assert calc.compute_ratio() == pytest.approx(0.20, abs=0.01)

    def test_density_medium_when_between_40_and_70_percent(self):
        """T-07-02a: 55 kendaraan dari kapasitas 100 = 55% → Medium."""
        calc = DensityCalculator(camera_id="CAM-001", road_capacity=100)
        detections = [make_detection() for _ in range(55)]
        calc.aggregate(detections)

        assert calc.classify_level() == "Medium"
        assert calc.compute_ratio() == pytest.approx(0.55, abs=0.01)

    def test_density_high_when_above_70_percent(self):
        """T-07-02: 80 kendaraan dari kapasitas 100 = 80% → High."""
        calc = DensityCalculator(camera_id="CAM-001", road_capacity=100)
        detections = [make_detection() for _ in range(80)]
        calc.aggregate(detections)

        assert calc.classify_level() == "High"
        assert calc.compute_ratio() == pytest.approx(0.80, abs=0.01)

    def test_density_zero_capacity_does_not_raise(self):
        """T-07-03: road_capacity=0 tidak boleh ZeroDivisionError, return 0.0."""
        calc = DensityCalculator(camera_id="CAM-001", road_capacity=0)
        detections = [make_detection() for _ in range(10)]
        calc.aggregate(detections)

        ratio = calc.compute_ratio()
        assert ratio == 0.0  # Tidak crash, return 0.0

    def test_density_ratio_clamped_to_1(self):
        """Jika kendaraan melebihi kapasitas, ratio maksimal 1.0 (tidak lebih)."""
        calc = DensityCalculator(camera_id="CAM-001", road_capacity=10)
        detections = [make_detection() for _ in range(50)]
        calc.aggregate(detections)

        ratio = calc.compute_ratio()
        assert ratio == pytest.approx(1.0, abs=0.01)
