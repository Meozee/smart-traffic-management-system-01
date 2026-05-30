"""Unit tests for layer1_cv CV module classes and utilities."""

from datetime import datetime, timezone

import numpy as np

from layer1_cv.cv_module import Detection, VideoCapture, VehicleDetector


def test_detection_to_dict_and_validation():
    """Detection should serialize correctly and validate confidence/bbox."""
    detection = Detection(
        bbox=[10.0, 20.0, 110.0, 120.0],
        confidence=0.85,
        class_id=2,
        vehicle_type="Car",
        direction_flow="Inbound",
        timestamp=datetime.now(timezone.utc)
    )

    serialized = detection.to_dict()
    assert serialized["vehicle_type"] == "Car"
    assert serialized["direction"] == "Inbound"
    assert serialized["confidence"] == 0.85
    assert detection.is_valid()


def test_detection_is_invalid_for_low_confidence_or_bad_bbox():
    """is_valid should reject detections with low confidence or malformed bbox."""
    low_conf = Detection(
        bbox=[10.0, 20.0, 110.0, 120.0],
        confidence=0.2,
        class_id=2,
        vehicle_type="Car",
        direction_flow="Inbound",
        timestamp=datetime.now(timezone.utc)
    )
    assert not low_conf.is_valid()

    bad_bbox = Detection(
        bbox=[10.0, 20.0],
        confidence=0.9,
        class_id=2,
        vehicle_type="Car",
        direction_flow="Inbound",
        timestamp=datetime.now(timezone.utc)
    )
    assert not bad_bbox.is_valid()


def test_video_capture_preprocess_transforms_frame():
    """VideoCapture.preprocess should resize and normalize a BGR frame."""
    video_capture = VideoCapture("dummy")
    dummy_frame = np.ones((100, 100, 3), dtype=np.uint8) * 255

    processed = video_capture.preprocess(dummy_frame)
    assert processed is not None
    assert processed.shape == (640, 640, 3)
    assert processed.dtype == np.float32
    assert processed.max() <= 1.0 and processed.min() >= 0.0


def test_vehicle_detector_classify_and_direction(monkeypatch):
    """VehicleDetector classify and direction helpers should behave correctly."""
    monkeypatch.setattr(VehicleDetector, "load_model", lambda self: None)
    detector = VehicleDetector("dummy_path")

    assert detector.classify(2) == "Car"
    assert detector.classify(3) == "Motorcycle"
    assert detector.classify(999) == "Unknown"

    # First call should initialize tracking and return Unknown
    first = detector.get_direction([100.0, 0.0, 200.0, 100.0], track_id=1)
    assert first == "Unknown"

    # Second call, moving across the virtual line at x=320 should be inbound
    second = detector.get_direction([400.0, 0.0, 500.0, 100.0], track_id=1)
    assert second == "Inbound"
