"""
Integration tests for Alerts API endpoints (T-08-01 .. T-08-03)
"""
from datetime import datetime, timezone
from fastapi import status

from layer2_backend import models


def create_camera(db_session, camera_id="CAM-ALERT-001"):
    camera = models.Camera(
        camera_id=camera_id,
        location_name="Alert Camera",
        road_capacity=100,
        direction="Bidirectional",
        status="active"
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    return camera


def test_internal_alert_create_idempotent(test_client, db_session):
    """Internal POST should create alert or return existing (idempotent)."""
    camera = create_camera(db_session)

    payload = {
        "density_id": 999,
        "camera_id": camera.camera_id,
        "message": "High density detected",
        "density_level": "High",
        "alert_type": "High Density",
        "severity": "High",
        "acknowledged": False
    }

    headers = {"X-Internal-Key": "stms-internal-key-2025"}

    r1 = test_client.post("/api/v1/alerts/internal", json=payload, headers=headers)
    assert r1.status_code == status.HTTP_201_CREATED
    body1 = r1.json()
    assert body1["density_id"] == 999

    # second call should be idempotent and return 200 with same alert
    r2 = test_client.post("/api/v1/alerts/internal", json=payload, headers=headers)
    assert r2.status_code == status.HTTP_200_OK
    body2 = r2.json()
    assert body2["alert_id"] == body1["alert_id"]


def test_get_alerts_and_acknowledge_flow(test_client, supervisor_headers, db_session):
    """Supervisor can list alerts and acknowledge when permitted."""
    camera = create_camera(db_session, camera_id="CAM-ALERT-002")

    # create alert via internal endpoint
    payload = {
        "density_id": 1001,
        "camera_id": camera.camera_id,
        "message": "Detector triggered",
        "density_level": "High",
        "alert_type": "High Density",
        "severity": "High",
        "acknowledged": False
    }
    headers_internal = {"X-Internal-Key": "stms-internal-key-2025"}
    r = test_client.post("/api/v1/alerts/internal", json=payload, headers=headers_internal)
    assert r.status_code in (200, 201)
    alert = r.json()

    # Supervisor can GET active alerts
    r_get = test_client.get("/api/v1/alerts", headers=supervisor_headers)
    assert r_get.status_code == status.HTTP_200_OK
    assert any(a["alert_id"] == alert["alert_id"] for a in r_get.json())

    # Supervisor can acknowledge (require_role allows supervisor)
    ack_resp = test_client.post(f"/api/v1/alerts/{alert['alert_id']}/acknowledge", headers=supervisor_headers)
    assert ack_resp.status_code == status.HTTP_200_OK
    ack_body = ack_resp.json()
    assert ack_body["acknowledged"] is True

    # A second acknowledge should return 400
    ack2 = test_client.post(f"/api/v1/alerts/{alert['alert_id']}/acknowledge", headers=supervisor_headers)
    assert ack2.status_code == status.HTTP_400_BAD_REQUEST
