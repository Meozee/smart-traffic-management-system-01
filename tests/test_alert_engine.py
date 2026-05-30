"""Unit tests for AlertEngine logic in layer1_cv."""

import requests

from layer1_cv.alert_engine import AlertEngine


def test_check_threshold_returns_true_for_high():
    """AlertEngine should identify High density levels as alert-worthy."""
    engine = AlertEngine(api_base_url="http://localhost:8000")
    assert engine.check_threshold("High") is True
    assert engine.check_threshold("Medium") is False
    assert engine.check_threshold("Low") is False


def test_create_alert_payload_contains_expected_fields():
    """create_alert should return data ready for backend posting."""
    engine = AlertEngine()
    payload = engine.create_alert(
        density_id=123,
        camera_id="CAM-001",
        density_level="High",
        total_vehicles=45
    )

    assert payload["density_id"] == 123
    assert payload["camera_id"] == "CAM-001"
    assert payload["density_level"] == "High"
    assert "message" in payload
    assert payload["acknowledged"] is False


def test_dispatch_calls_backend(monkeypatch):
    """dispatch should return True when backend responds with 200/201."""
    engine = AlertEngine(api_base_url="http://localhost:8000")

    class DummyResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = "ok"

    def dummy_post(url, json, timeout):
        assert url.endswith("/api/v1/alerts/internal")
        assert json["density_id"] == 123
        return DummyResponse(201)

    monkeypatch.setattr(requests, "post", dummy_post)
    payload = engine.create_alert(123, "CAM-001", "High", total_vehicles=75)
    assert engine.dispatch(payload) is True


def test_should_create_alert_only_once_per_density_id():
    """should_create_alert should only allow unique density IDs per process lifetime."""
    engine = AlertEngine()
    assert engine.should_create_alert(101) is True
    engine.mark_alerted(101)
    assert engine.should_create_alert(101) is False
