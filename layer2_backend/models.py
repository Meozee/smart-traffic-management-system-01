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
# Represents a traffic monitoring point with directional flow configuration.
# ═══════════════════════════════════════════════════════════════════════════════

class Camera(Base):
    """
    Represents a single traffic monitoring camera/sensor.
    
    Attributes:
        camera_id: Unique identifier (e.g., "CAM-001")
        location_name: Descriptive name (e.g., "Jl. Diponegoro - Intersection A")
        segment_id: Optional road segment identifier
        road_capacity: Maximum vehicles per interval (default: 50)
        direction: Traffic flow direction (Inbound / Outbound / Bidirectional)
        status: Camera operational status (active / inactive / maintenance)
        created_at: Timestamp when camera was registered
    """
    
    __tablename__ = "camera"
    
    camera_id = Column(String(20), primary_key=True)
    location_name = Column(String(100), nullable=False)
    segment_id = Column(String(20), nullable=True)
    road_capacity = Column(Integer, nullable=False, default=50)
    direction = Column(String(20), nullable=False, default="Bidirectional")
    status = Column(String(10), nullable=False, default='active')
    stream_url = Column(String(255), nullable=True)       # RTSP / DroidCam / file path
    virtual_line_y = Column(Integer, nullable=True, default=300)  # counting line Y-position (px)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Relationships to other tables
    vehicle_detections = relationship(
        "VehicleDetection",
        back_populates="camera",
        cascade="all, delete-orphan",
        foreign_keys="VehicleDetection.camera_id"
    )
    traffic_densities = relationship(
        "TrafficDensity",
        back_populates="camera",
        cascade="all, delete-orphan",
        foreign_keys="TrafficDensity.camera_id"
    )
    alerts = relationship(
        "Alert",
        back_populates="camera",
        cascade="all, delete-orphan",
        foreign_keys="Alert.camera_id"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Camera(camera_id={self.camera_id!r}, location_name={self.location_name!r}, "
            f"direction={self.direction!r}, status={self.status!r})>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: VEHICLE_DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
# Records each individual vehicle detection with confidence score and bounding box.
# ═══════════════════════════════════════════════════════════════════════════════

class VehicleDetection(Base):
    """
    Records a single vehicle detection event.
    
    Attributes:
        detection_id: Unique auto-incrementing identifier
        camera_id: Reference to Camera (FK)
        timestamp: When detection occurred (UTC)
        vehicle_type: Category (Car / Motorcycle / Truck / Bus / Unknown)
        count: Number of vehicles detected (default: 1, ≥ 0)
        direction: Direction of flow (Inbound / Outbound)
        bbox_data: Optional bounding box coordinates as JSON
        confidence: Model confidence score (0.0-1.0, nullable)
    """
    
    __tablename__ = "vehicle_detection"
    
    detection_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    vehicle_type = Column(String(20), nullable=False)
    count = Column(Integer, nullable=False, default=1)
    direction = Column(String(10), nullable=False)
    bbox_data = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('count >= 0', name='check_detection_count_non_negative'),
        CheckConstraint('confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)',
                       name='check_detection_confidence_range'),
        Index('idx_detection_camera_timestamp', 'camera_id', 'timestamp'),
    )
    
    # Relationships
    camera = relationship("Camera", back_populates="vehicle_detections", foreign_keys=[camera_id])
    
    def __repr__(self) -> str:
        return (
            f"<VehicleDetection(detection_id={self.detection_id}, camera_id={self.camera_id!r}, "
            f"vehicle_type={self.vehicle_type!r}, direction={self.direction!r}, "
            f"confidence={self.confidence})>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: TRAFFIC_DENSITY
# ═══════════════════════════════════════════════════════════════════════════════
# Aggregated metrics calculated at regular intervals (default: 15 minutes).
# ═══════════════════════════════════════════════════════════════════════════════

class TrafficDensity(Base):
    """
    Aggregated traffic density metrics for an interval.
    
    Attributes:
        density_id: Unique auto-incrementing identifier
        camera_id: Reference to Camera (FK)
        interval_start: Start of aggregation interval (UTC)
        interval_end: End of aggregation interval (UTC)
        total_vehicles: Total vehicle count in interval (≥ 0)
        inflow_count: Vehicles flowing in/entering (≥ 0)
        outflow_count: Vehicles flowing out/exiting (≥ 0)
        density_ratio: Ratio of vehicles to road capacity (0.0-1.0)
        density_level: Classification (Low / Medium / High)
    """
    
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
    
    # Constraints
    __table_args__ = (
        CheckConstraint('total_vehicles >= 0', name='check_density_total_non_negative'),
        CheckConstraint('inflow_count >= 0', name='check_density_inflow_non_negative'),
        CheckConstraint('outflow_count >= 0', name='check_density_outflow_non_negative'),
        CheckConstraint('density_ratio IS NULL OR (density_ratio >= 0.0 AND density_ratio <= 1.0)',
                       name='check_density_ratio_range'),
        Index('idx_density_camera_interval', 'camera_id', 'interval_start', 'interval_end'),
        Index('idx_density_level', 'density_level'),
    )
    
    # Relationships
    camera = relationship("Camera", back_populates="traffic_densities", foreign_keys=[camera_id])
    alert = relationship(
        "Alert",
        back_populates="traffic_density",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="Alert.density_id"
    )
    
    def __repr__(self) -> str:
        return (
            f"<TrafficDensity(density_id={self.density_id}, camera_id={self.camera_id!r}, "
            f"interval={self.interval_start.isoformat() if self.interval_start else None} "
            f"to {self.interval_end.isoformat() if self.interval_end else None}, "
            f"density_level={self.density_level!r}, ratio={self.density_ratio})>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: ALERT
# ═══════════════════════════════════════════════════════════════════════════════
# High-density traffic alerts with unique constraint on density_id (1:1 relation).
# ═══════════════════════════════════════════════════════════════════════════════

class Alert(Base):
    """
    Traffic alert triggered when density level is HIGH.
    
    Enforces 1:1 relationship: one density_id can only have ONE alert.
    This prevents duplicate alert creation for same density measurement.
    
    Attributes:
        alert_id: Unique auto-incrementing identifier
        density_id: Reference to TrafficDensity (FK, UNIQUE) — enforces 1:1 relation
        camera_id: Reference to Camera (FK)
        triggered_at: When alert was created (UTC, server_default=now)
        density_level: Traffic level at trigger (default: High)
        alert_type: Type of alert (default: "High Density")
        severity: Alert severity level (default: "High")
        message: Human-readable alert message
        acknowledged: Whether alert has been acknowledged by user (default: False)
        acknowledged_at: Timestamp when user acknowledged (nullable)
        acknowledged_by: Username of user who acknowledged (nullable)
    """
    
    __tablename__ = "alert"
    
    alert_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    density_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("traffic_density.density_id", ondelete="CASCADE"),
                       nullable=False)
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False)
    triggered_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    density_level = Column(String(10), nullable=False, default='High')
    alert_type = Column(String(50), nullable=False, default='High Density')
    severity = Column(String(20), nullable=False, default='High')
    message = Column(String(500), nullable=False)
    acknowledged = Column(Boolean, nullable=False, default=False)
    acknowledged_at = Column(TIMESTAMP, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    
    # Constraints: UNIQUE on density_id enforces 1:1 relation Alert ↔ TrafficDensity
    __table_args__ = (
        UniqueConstraint('density_id', name='unique_alert_per_density'),
        Index('idx_alert_camera_triggered', 'camera_id', 'triggered_at'),
        Index('idx_alert_acknowledged', 'acknowledged'),
    )
    
    # Relationships
    traffic_density = relationship("TrafficDensity", back_populates="alert", foreign_keys=[density_id])
    camera = relationship("Camera", back_populates="alerts", foreign_keys=[camera_id])
    
    def __repr__(self) -> str:
        return (
            f"<Alert(alert_id={self.alert_id}, density_id={self.density_id}, "
            f"camera_id={self.camera_id!r}, severity={self.severity!r}, "
            f"acknowledged={self.acknowledged})>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE: USER_ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════════
# User credentials and role-based access control.
# ═══════════════════════════════════════════════════════════════════════════════

class UserAccount(Base):
    """
    User account for STMS dashboard access.
    
    Attributes:
        user_id: Unique identifier (e.g., "user-001")
        username: Login username (UNIQUE)
        password_hash: Bcrypt hashed password (cost ≥ 12)
        role: User role level (supervisor / management / admin)
        created_at: Account creation timestamp (UTC, server_default=now)
        last_login: Last login timestamp (nullable, updated by auth.py)
    """
    
    __tablename__ = "user_account"
    
    user_id = Column(String(50), primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    last_login = Column(TIMESTAMP, nullable=True)
    
    # Constraints
    __table_args__ = (
        Index('idx_user_username', 'username'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<UserAccount(user_id={self.user_id!r}, username={self.username!r}, "
            f"role={self.role!r}, created_at={self.created_at})>"
        )