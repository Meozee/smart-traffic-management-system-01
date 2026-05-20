from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import cameras, auth, detections
from .routers import stream

# Inisialisasi FastAPI dengan metadata proyekmu
app = FastAPI(
    title="Smart Traffic Monitoring System (STMS) API",
    description="Backend API untuk analisis tren lalu lintas di area wisata",
    version="1.0.0"
)

# TAMBAHKAN INI: CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mengizinkan semua sumber (untuk development)
    allow_methods=["*"],
    allow_headers=["*"],
)

# Perintah untuk membuat tabel saat aplikasi dijalankan (jika belum ada)
Base.metadata.create_all(bind=engine)

# Daftarkan router
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(detections.router)
app.include_router(stream.router)
# Root endpoint
@app.get("/")
def read_root():
    return {
        "message": "Welcome to STMS API",
        "status": "Running",
        "version": "v1"
    }

# Endpoint health check
@app.get("/api/v1/health")
def health_check():
    return {"status": "healthy", "database": "connected"}