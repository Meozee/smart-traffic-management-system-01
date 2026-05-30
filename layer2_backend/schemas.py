"""
Pydantic v2 Data Validation Schemas for STMS

Defines request/response models for all API endpoints.
Includes validators for enum fields (direction, role, density_level).
All response models use ConfigDict(from_attributes=True) for ORM compatibility.
"""

from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS: CAMERA
# ═══════════════════════════════════════════════════════════════════════════════

class CameraCreate(BaseModel):
    """Request schema for creating a new camera."""
    camera_id: str
    location_name: str
    road_capacity: int = 50
    direction: str = "Bidirectional"
    status: str = "active"
    segment_id: Optional[str] = None
    
    @field_validator('direction')
    @classmethod
    def validate_direction(cls, v: str) -> str:
        valid = {"Inbound", "Outbound", "Bidirectional"}
        if v not in valid:
            raise ValueError(f"direction must be one of {valid}, got {v}")
        return v


class CameraUpdate(BaseModel):
    """Request schema for updating a camera."""
    location_name: Optional[str] = None
    road_capacity: Optional[int] = None
    direction: Optional[str] = None
    status: Optional[str] = None
    
    @field_validator('direction')
    @classmethod
    def validate_direction(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid = {"Inbound", "Outbound", "Bidirectional"}
        if v not in valid:
            raise ValueError(f"direction must be one of {valid}, got {v}")
        return v


class CameraResponse(BaseModel):
    """Response schema for camera data."""
    camera_id: str
    location_name: str
    road_capacity: int
    direction: str
    status: str
    created_at: datetime
    segment_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS: VEHICLE DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class DetectionCreate(BaseModel):
    """Request schema for creating a vehicle detection."""
    camera_id: str
    timestamp: datetime
    vehicle_type: str
    count: int = 1
    direction: str
    bbox_data: Optional[dict] = None
    confidence: Optional[float] = None


class DetectionResponse(DetectionCreate):
    """Response schema for vehicle detection."""
    detection_id: int
    
    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS: TRAFFIC DENSITY
# ═══════════════════════════════════════════════════════════════════════════════

class DensityResponse(BaseModel):
    """Response schema for traffic density metrics."""
    density_id: int
    camera_id: str
    interval_start: datetime
    interval_end: datetime
    total_vehicles: int
    inflow_count: int
    outflow_count: int
    density_ratio: Optional[float]
    density_level: str
    
    @field_validator('density_level')
    @classmethod
    def validate_density_level(cls, v: str) -> str:
        valid = {"Low", "Medium", "High"}
        if v not in valid:
            raise ValueError(f"density_level must be one of {valid}, got {v}")
        return v
    
    model_config = ConfigDict(from_attributes=True)


class ReportSummary(BaseModel):
    """Summary statistics for traffic report."""
    total_vehicles: int
    average_density_ratio: float
    peak_hour: Optional[str] = None
    peak_day: Optional[str] = None
    density_distribution: dict


class DensityHistoryResponse(BaseModel):
    """Response schema for density history with summary."""
    data: List[DensityResponse]
    summary: ReportSummary


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS: ALERT
# ═══════════════════════════════════════════════════════════════════════════════

class AlertResponse(BaseModel):
    """Response schema for traffic alert."""
    alert_id: int
    density_id: int
    camera_id: str
    triggered_at: datetime
    density_level: str
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    @field_validator('density_level')
    @classmethod
    def validate_density_level(cls, v: str) -> str:
        valid = {"Low", "Medium", "High"}
        if v not in valid:
            raise ValueError(f"density_level must be one of {valid}, got {v}")
        return v
    
    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledgeRequest(BaseModel):
    """Request schema for acknowledging an alert."""
    acknowledged_by: str


class AlertAcknowledgeResponse(BaseModel):
    """Response schema for acknowledged alert."""
    alert_id: int
    acknowledged: bool
    acknowledged_at: datetime
    acknowledged_by: str
    
    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS: AUTHENTICATION & USER
# ═══════════════════════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Request schema for user registration."""
    username: str
    password: str
    role: str = "supervisor"
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {"supervisor", "management", "admin"}
        if v not in valid:
            raise ValueError(f"role must be one of {valid}, got {v}")
        return v


class UserLogin(BaseModel):
    """Request schema for user login."""
    username: str
    password: str


class UserResponse(BaseModel):
    """Response schema for user account."""
    user_id: str
    username: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {"supervisor", "management", "admin"}
        if v not in valid:
            raise ValueError(f"role must be one of {valid}, got {v}")
        return v
    
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Response schema for JWT token."""
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class TokenData(BaseModel):
    """Token claim data."""
    username: Optional[str] = None
    role: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS: REPORT & EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

class ReportExportParams(BaseModel):
    """Request schema for exporting traffic report."""
    format: str
    start_date: datetime
    end_date: datetime
    camera_id: Optional[str] = None
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v: str) -> str:
        valid = {"pdf", "csv"}
        if v not in valid:
            raise ValueError(f"format must be one of {valid}, got {v}")
        return v
