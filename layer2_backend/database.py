"""
Smart Traffic Monitoring System (STMS) — Database Configuration Module

Handles SQLAlchemy engine creation, session management, and database initialization.
All configuration (connection string) is loaded from config.py which reads from .env
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import bcrypt
from . import models, config

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

# Create SQLAlchemy engine using connection string from config.py
engine = create_engine(
    config.DATABASE_URL,
    echo=False,  # Set to True untuk debug SQL queries
    pool_pre_ping=True,  # Test connection sebelum menggunakan dari pool
    pool_recycle=3600  # Recycle connection setiap 1 jam
)

# Create SessionLocal factory untuk membuat database session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY FOR FASTAPI
# ═══════════════════════════════════════════════════════════════════════════════

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency untuk mendapatkan database session.
    Digunakan dengan Depends(get_db) di endpoint router.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    """
    Initialize database: create all tables jika belum ada.
    
    Dijalankan saat application startup (lihat main.py startup event).
    Tidak membuat user admin default lagi — password harus di-hash dengan bcrypt.
    """
    models.Base.metadata.create_all(bind=engine)
    print("✅ Database tables initialized successfully.")


def create_default_admin(username: str = "admin", password: str = "admin123") -> None:
    """
    Create default admin user dengan bcrypt-hashed password.
    
    Args:
        username: Admin username (default: "admin")
        password: Admin password plaintext (akan di-hash dengan bcrypt)
    
    NOTE: Fungsi ini hanya untuk development/testing.
          Di production, gunakan manual SQL atau admin panel untuk create user.
    """
    from datetime import datetime
    
    if isinstance(password, str):
        password = password.encode("utf-8")
    password = password[:72]
    password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")
    
    db = SessionLocal()
    try:
        # Cek apakah admin sudah ada
        existing_admin = db.query(models.UserAccount).filter(
            models.UserAccount.username == username
        ).first()
        
        if existing_admin:
            print(f"ℹ️  User '{username}' sudah ada di database.")
            return
        
        # Buat user baru dengan role 'admin'
        new_admin = models.UserAccount(
            user_id="USR-ADMIN-001",
            username=username,
            password_hash=password_hash,
            role="admin",
            created_at=datetime.utcnow()
        )
        
        db.add(new_admin)
        db.commit()
        
        print(f"✅ Default admin user '{username}' created successfully.")
        print(f"   Password: {password.decode('utf-8')} (HARUS diganti saat first login di production)")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating default admin: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # Script untuk manual database setup (jalankan dari CLI jika perlu)
    print("Initializing STMS database...")
    init_db()
    create_default_admin()
    print("✅ Database setup complete!")