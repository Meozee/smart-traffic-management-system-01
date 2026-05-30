"""
Integration tests for Cameras API and IE compatibility (T-09-01 .. T-09-03)
"""
from datetime import datetime, timezone
from fastapi import status
import os

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


def test_get_cameras_returns_list(test_client, supervisor_headers, db_session):
    """GET /api/v1/cameras should return cameras with expected fields."""
    cam = create_camera(db_session, camera_id="CAM-API-001")

    r = test_client.get("/api/v1/cameras", headers=supervisor_headers)
    assert r.status_code == status.HTTP_200_OK

    cameras = r.json()
    assert isinstance(cameras, list)
    assert len(cameras) >= 1
    cam0 = cameras[0]
    assert "camera_id" in cam0
    assert "location_name" in cam0
    assert "status" in cam0
    assert "road_capacity" in cam0


class TestIECompatibility:
    """T-09-03: Internet Explorer compatibility warning exists in HTML files."""

    def test_dashboard_html_contains_ie_detection_script(self):
        """Dashboard should contain IE detection code."""
        dashboard_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'layer3_dashboard', 'pages', 'dashboard.html'
        )
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'MSInputMethodContext' in content or 'document.documentMode' in content

    def test_login_html_contains_ie_detection_script(self):
        """Login page should contain IE detection code."""
        login_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'layer3_dashboard', 'login.html'
        )
        with open(login_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'MSInputMethodContext' in content or 'document.documentMode' in content
