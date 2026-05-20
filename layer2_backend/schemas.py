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