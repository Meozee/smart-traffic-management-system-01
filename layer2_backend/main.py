from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from .database import engine, Base
from .routers import cameras, auth, detections, stream
from .init_cameras import init_default_cameras
from .tasks import calculate_density_task  # Impor task kita

app = FastAPI(
    title="Smart Traffic Monitoring System (STMS) API",
    description="Backend API untuk analisis tren lalu lintas di area wisata",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
init_default_cameras()

# Inisialisasi Scheduler
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    # Jalankan job setiap 15 menit
    scheduler.add_job(calculate_density_task, 'interval', minutes=15)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(detections.router)
app.include_router(stream.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to STMS API", "status": "Running", "version": "v1"}