"""Integration tests for STMS density API endpoints."""

from datetime import datetime, timezone, timedelta
from fastapi import status

from layer2_backend import models


def create_camera(db_session, camera_id="CAM-001"):
    camera = models.Camera(
        camera_id=camera_id,
        location_name="Test Camera",
        road_capacity=100,
        direction="Bidirectional",
        status="active"
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    return camera


def create_density(db_session, camera_id, interval_start, total_vehicles, density_level):
    density = models.TrafficDensity(
        camera_id=camera_id,
        interval_start=interval_start,
        interval_end=interval_start + timedelta(minutes=15),
        total_vehicles=total_vehicles,
        inflow_count=total_vehicles // 2,
        outflow_count=total_vehicles // 2,
        density_ratio=min(total_vehicles / 100.0, 1.0),
        density_level=density_level
    )
    db_session.add(density)
    db_session.commit()
    db_session.refresh(density)
    return density


def test_realtime_density_returns_latest_records(test_client, supervisor_headers, db_session):
    """Realtime endpoint should return the latest density record per camera."""
    camera = create_camera(db_session)
    older_start = datetime.now(timezone.utc) - timedelta(hours=1)
    create_density(db_session, camera.camera_id, older_start, 10, "Low")
    latest_start = datetime.now(timezone.utc)
    create_density(db_session, camera.camera_id, latest_start, 80, "High")

    response = test_client.get("/api/v1/density/realtime", headers=supervisor_headers)
    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    item = payload[0]
    assert item["camera_id"] == camera.camera_id
    assert item["total_vehicles"] == 80
    assert item["density_level"] == "High"


def test_history_density_requires_management_or_admin(test_client, supervisor_headers, db_session):
    """History endpoint should reject supervisor role with 403 forbidden."""
    camera = create_camera(db_session)
    start = datetime.now(timezone.utc) - timedelta(days=1)
    end = datetime.now(timezone.utc)
    create_density(db_session, camera.camera_id, start, 20, "Low")

    response = test_client.get(
        "/api/v1/density/history",
        headers=supervisor_headers,
        params={
            "start_date": start.isoformat(),
            "end_date": end.isoformat()
        }
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_history_density_returns_summary_for_management(test_client, management_headers, db_session):
    """History endpoint should return data and summary for management role."""
    camera = create_camera(db_session)
    start = datetime.now(timezone.utc) - timedelta(days=1)
    middle = start + timedelta(hours=1)
    create_density(db_session, camera.camera_id, start, 25, "Low")
    create_density(db_session, camera.camera_id, middle, 75, "High")

    response = test_client.get(
        "/api/v1/density/history",
        headers=management_headers,
        params={
            "start_date": start.isoformat(),
            "end_date": datetime.now(timezone.utc).isoformat()
        }
    )
    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    assert "data" in payload
    assert "summary" in payload
    assert len(payload["data"]) == 2
    assert payload["summary"]["total_vehicles"] == 100
    assert payload["summary"]["average_density_ratio"] >= 0.0


def test_history_density_invalid_date_range_returns_bad_request(test_client, management_headers):
    """History endpoint should return 400 when start_date is after end_date."""
    now = datetime.now(timezone.utc)
    response = test_client.get(
        "/api/v1/density/history",
        headers=management_headers,
        params={
            "start_date": now.isoformat(),
            "end_date": (now - timedelta(days=1)).isoformat()
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
