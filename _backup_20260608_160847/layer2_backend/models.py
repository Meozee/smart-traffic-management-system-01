"""
SQLAlchemy ORM Models for Smart Traffic Monitoring System (STMS)

Defines 5 core tables with proper constraints, relationships, and validation:
- Camera: Monitoring points with direction (Inbound/Outbound/Bidirectional)
- VehicleDetection: Individual vehicle detections with bbox and confidence
- TrafficDensity: Aggregated density metrics at regular intervals
- Alert: High-density alerts with acknowledge tracking (1:1 relation to TrafficDensity)
- UserAccount: User credentials and role-based access (supervisor/management/admin)

All timestamps use UTC timezone via server_default=func.now().
Foreign keys include CASCADE delete to maintain referential integrity.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, TIMESTAMP,
    ForeignKey, BigInteger, JSON, UniqueConstraint, CheckConstraint,
    Index, func
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: CAMERA
# ═══════════════════════════════════════════════════════════════════════════════

class Camera(Base):
    """
    Represents a single traffic monitoring camera/sensor.
    """
    __tablename__ = "camera"
    
    camera_id = Column(String(20), primary_key=True)
    location_name = Column(String(100), nullable=False)
    segment_id = Column(String(20), nullable=True)
    road_capacity = Column(Integer, nullable=False, default=50)
    direction = Column(String(20), nullable=False, default="Bidirectional")
    status = Column(String(10), nullable=False, default='active')
    stream_url = Column(String(255), nullable=True)
    
    # --- Pengaturan Garis Virtual Interaktif (4 Titik Koordinat) ---
    line_x1 = Column(Integer, nullable=False, default=100)
    line_y1 = Column(Integer, nullable=False, default=300)
    line_x2 = Column(Integer, nullable=False, default=500)
    line_y2 = Column(Integer, nullable=False, default=300)

    # --- Pengaturan Kepadatan & AI Per-Kamera ---
    low_density_threshold = Column(Float, nullable=False, default=0.40)
    high_density_threshold = Column(Float, nullable=False, default=0.70)
    confidence_tolerance = Column(Float, nullable=False, default=0.50)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Relationships
    vehicle_detections = relationship(
        "VehicleDetection", back_populates="camera", cascade="all, delete-orphan"
    )
    traffic_densities = relationship(
        "TrafficDensity", back_populates="camera", cascade="all, delete-orphan"
    )
    alerts = relationship(
        "Alert", back_populates="camera", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Camera(camera_id={self.camera_id!r}, location_name={self.location_name!r})>"


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: VEHICLE_DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class VehicleDetection(Base):
    __tablename__ = "vehicle_detection"
    
    detection_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    vehicle_type = Column(String(20), nullable=False)
    count = Column(Integer, nullable=False, default=1)
    direction = Column(String(10), nullable=False)
    bbox_data = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    
    __table_args__ = (
        CheckConstraint('count >= 0', name='check_detection_count_non_negative'),
        CheckConstraint('confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)', name='check_detection_confidence_range'),
        Index('idx_detection_camera_timestamp', 'camera_id', 'timestamp'),
    )
    
    camera = relationship("Camera", back_populates="vehicle_detections")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: TRAFFIC_DENSITY
# ═══════════════════════════════════════════════════════════════════════════════

class TrafficDensity(Base):
    __tablename__ = "traffic_density"
    
    density_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False)
    interval_start = Column(TIMESTAMP, nullable=False)
    interval_end = Column(TIMESTAMP, nullable=False)
    total_vehicles = Column(Integer, nullable=False, default=0)
    inflow_count = Column(Integer, nullable=False, default=0)
    outflow_count = Column(Integer, nullable=False, default=0)
    density_ratio = Column(Float, nullable=True)
    density_level = Column(String(10), nullable=False)
    
    __table_args__ = (
        CheckConstraint('total_vehicles >= 0', name='check_density_total_non_negative'),
        CheckConstraint('inflow_count >= 0', name='check_density_inflow_non_negative'),
        CheckConstraint('outflow_count >= 0', name='check_density_outflow_non_negative'),
        CheckConstraint('density_ratio IS NULL OR (density_ratio >= 0.0 AND density_ratio <= 1.0)', name='check_density_ratio_range'),
        Index('idx_density_camera_interval', 'camera_id', 'interval_start', 'interval_end'),
        Index('idx_density_level', 'density_level'),
    )
    
    camera = relationship("Camera", back_populates="traffic_densities")
    alert = relationship("Alert", back_populates="traffic_density", cascade="all, delete-orphan", uselist=False)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: ALERT
# ═══════════════════════════════════════════════════════════════════════════════

class Alert(Base):
    __tablename__ = "alert"
    
    alert_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    density_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("traffic_density.density_id", ondelete="CASCADE"), nullable=False)
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False)
    triggered_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    density_level = Column(String(10), nullable=False, default='High')
    alert_type = Column(String(50), nullable=False, default='High Density')
    severity = Column(String(20), nullable=False, default='High')
    message = Column(String(500), nullable=False)
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_at = Column(TIMESTAMP, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    
    __table_args__ = (
        UniqueConstraint('density_id', name='unique_alert_per_density'),
        Index('idx_alert_camera_triggered', 'camera_id', 'triggered_at'),
        Index('idx_alert_acknowledged', 'acknowledged'),
    )
    
    traffic_density = relationship("TrafficDensity", back_populates="alert")
    camera = relationship("Camera", back_populates="alerts")


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: USER_ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════════

class UserAccount(Base):
    __tablename__ = "user_account"
    
    user_id = Column(String(50), primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    last_login = Column(TIMESTAMP, nullable=True)
    
    __table_args__ = (
        Index('idx_user_username', 'username'),
    )