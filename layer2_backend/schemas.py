from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ==========================
# SCHEMAS UNTUK KAMERA
# ==========================
class CameraBase(BaseModel):
    camera_id: str
    location_name: str
    segment_id: Optional[str] = None
    road_capacity: int
    status: Optional[str] = "active"
    stream_url: Optional[str] = None
    
    # --- FITUR BARU: Input posisi Y-Axis dari UI ---
    virtual_line_y: Optional[int] = 300 
    # -----------------------------------------------

class CameraCreate(CameraBase):
    pass

class CameraResponse(CameraBase):
    created_at: datetime

    class Config:
        from_attributes = True

# ==========================
# SCHEMAS UNTUK AUTH & USER
# ==========================
class UserCreate(BaseModel):
    username: str
    password: str
    role: str

class UserResponse(BaseModel):
    username: str
    role: str
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# ==========================
# SCHEMAS UNTUK DETECTIONS
# ==========================
class DetectionCreate(BaseModel):
    camera_id: str
    timestamp: datetime
    vehicle_type: str
    count: int
    direction: str
    bbox_data: Optional[dict] = None
    confidence: float

class DetectionResponse(DetectionCreate):
    detection_id: int
    
    class Config:
        from_attributes = True

# ==========================
# SCHEMAS UNTUK TRAFFIC DENSITY
# ==========================
class TrafficDensityCreate(BaseModel):
    camera_id: str
    interval_start: datetime
    interval_end: datetime
    total_vehicles: int
    inflow_count: int
    outflow_count: int
    density_ratio: float
    density_level: str

class TrafficDensityResponse(TrafficDensityCreate):
    density_id: int
    
    class Config:
        from_attributes = True


# ==========================
# SCHEMAS UNTUK ALERTS
# ==========================
class AlertCreate(BaseModel):
    camera_id: str
    message: str

class AlertResponse(AlertCreate):
    alert_id: int
    is_read: Optional[bool] = False
    timestamp: datetime

    class Config:
        from_attributes = True