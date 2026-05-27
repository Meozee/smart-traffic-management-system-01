from sqlalchemy import Column, String, Integer, Float, Boolean, TIMESTAMP, ForeignKey, BigInteger, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Camera(Base):
    __tablename__ = "camera" 
    camera_id = Column(String(20), primary_key=True)
    location_name = Column(String(100), nullable=False)
    segment_id = Column(String(20))
    road_capacity = Column(Integer, nullable=False)
    status = Column(String(10), default='active')
    stream_url = Column(String(255), nullable=True) 
    
    # --- FITUR BARU: Dynamic Virtual Line ---
    virtual_line_y = Column(Integer, default=300) 
    # ----------------------------------------
    
    created_at = Column(TIMESTAMP, server_default=func.now())

class VehicleDetection(Base):
    __tablename__ = "vehicle_detection"
    detection_id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Tambahan ondelete="CASCADE" agar jika kamera dihapus/di-reset, data historinya ikut terhapus otomatis
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE")) 
    
    timestamp = Column(TIMESTAMP, nullable=False)
    vehicle_type = Column(String(20), nullable=False)
    count = Column(Integer, nullable=False)
    direction = Column(String(10), nullable=False)
    bbox_data = Column(JSON, nullable=True)
    confidence = Column(Float)

class TrafficDensity(Base):
    __tablename__ = "traffic_density"
    density_id = Column(BigInteger, primary_key=True, autoincrement=True) 
    
    # Tambahan ondelete="CASCADE" 
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE")) 
    
    interval_start = Column(TIMESTAMP, nullable=False) 
    interval_end = Column(TIMESTAMP, nullable=False) 
    total_vehicles = Column(Integer, nullable=False) 
    inflow_count = Column(Integer, nullable=False) 
    outflow_count = Column(Integer, nullable=False) 
    density_ratio = Column(Float) 
    density_level = Column(String(10), nullable=False) 

class UserAccount(Base):
    __tablename__ = "user_account"
    user_id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False) # supervisor/management/admin
    created_at = Column(TIMESTAMP, server_default=func.now())
    last_login = Column(TIMESTAMP, nullable=True)

class Alert(Base):
    __tablename__ = "alert"
    alert_id = Column(BigInteger, primary_key=True, autoincrement=True)
    camera_id = Column(String(20), ForeignKey("camera.camera_id", ondelete="CASCADE"))
    message = Column(String(255))
    timestamp = Column(TIMESTAMP, server_default=func.now()) # Menggunakan server_default untuk timestamp
    is_read = Column(Boolean, default=False)