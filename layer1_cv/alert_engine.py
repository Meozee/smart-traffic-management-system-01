"""
alert_engine.py
Layer 1 – Alert Engine
Implements AlertEngine to create and dispatch alert notifications to backend API.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class AlertEngine:
    """Monitor density level and create/dispatch alerts when necessary."""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url.rstrip('/')
        self._alerted_density_ids: set = set()

    def check_threshold(self, density_level: str) -> bool:
        """Return True only when density_level == 'High'."""
        return str(density_level) == 'High'

    def create_alert(
        self,
        density_id: int,
        camera_id: str,
        density_level: str,
        total_vehicles: int = 0
    ) -> dict:
        """Create alert dict ready to be dispatched or saved to DB."""
        return {
            "density_id": int(density_id),
            "camera_id": str(camera_id),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "density_level": str(density_level),
            "alert_type": "High Density",
            "severity": "High",
            "message": f"Traffic density at camera {camera_id} has reached HIGH level. Vehicle count: {total_vehicles}",
            "acknowledged": False
        }

    def dispatch(self, alert_data: dict) -> bool:
        """POST alert_data to backend endpoint POST /api/v1/alerts/internal."""
        url = f"{self.api_base_url}/api/v1/alerts/internal"
        try:
            resp = requests.post(url, json=alert_data, timeout=5)
            if resp.status_code in (200, 201):
                logger.info(f"Alert dispatched to backend: {url} (status={resp.status_code})")
                return True
            logger.warning(f"Alert dispatch returned status={resp.status_code}: {resp.text}")
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Alert dispatch failed: {e}")
            return False

    def should_create_alert(self, density_id: int) -> bool:
        """Return True if density_id has not been alerted in this process lifetime."""
        return int(density_id) not in self._alerted_density_ids

    def mark_alerted(self, density_id: int) -> None:
        """Mark density_id as alerted in in-memory cache."""
        try:
            self._alerted_density_ids.add(int(density_id))
        except Exception:
            logger.exception("Failed to mark density_id as alerted")
