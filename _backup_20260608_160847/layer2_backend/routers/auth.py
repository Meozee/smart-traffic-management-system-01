"""
Authentication Router for STMS

Handles user registration and login with JWT token generation.
All security configuration (SECRET_KEY, ALGORITHM, token expiry) is read from config.py
which loads from .env file.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from typing import Optional

from .. import database, models, schemas, config

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY CONFIGURATION (read from config.py)
# ═══════════════════════════════════════════════════════════════════════════════

SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

# Create router dengan prefix /api/v1/auth
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plaintext password terhadap bcrypt hash.
    
    Args:
        plain_password: Password yang diinput user
        hashed_password: Hash dari database
    
    Returns:
        True jika cocok, False jika tidak
    """
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash plaintext password menggunakan bcrypt.
    
    Args:
        password: Plaintext password dari user
    
    Returns:
        Bcrypt hash string (siap disimpan ke database)
    """
    if isinstance(password, str):
        password = password.encode("utf-8")
    password = password[:72]
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token dengan claims dari data dictionary.
    
    Args:
        data: Dictionary berisi claims (contoh: {"sub": "username", "role": "admin"})
        expires_delta: Optional custom expiry time (default: dari config.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Encode JWT dengan SECRET_KEY dan ALGORITHM dari config
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def get_db() -> Session:
    """FastAPI dependency untuk database session."""
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/register", response_model=schemas.UserResponse)
def register(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
) -> schemas.UserResponse:
    """
    Register user baru dengan username dan password.
    
    - Username harus unik
    - Password akan di-hash dengan bcrypt sebelum disimpan
    - Role: supervisor / management / admin (sesuai spesifikasi Form 3)
    
    Args:
        user: UserCreate schema dengan username, password, role
        db: Database session
    
    Returns:
        UserResponse dengan user_id, username, role (password_hash tidak dikembalikan)
    
    Raises:
        400: Username sudah terdaftar
    """
    # Cek apakah username sudah dipakai
    db_user = db.query(models.UserAccount).filter(
        models.UserAccount.username == user.username
    ).first()
    
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username sudah terdaftar. Gunakan username lain."
        )
    
    # Validasi role
    valid_roles = ["supervisor", "management", "admin"]
    if user.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role harus salah satu dari: {', '.join(valid_roles)}"
        )
    
    # Hash password dengan bcrypt
    hashed_password = get_password_hash(user.password)
    
    # Generate unique user_id
    user_id = f"USR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    # Buat user baru di database
    new_user = models.UserAccount(
        user_id=user_id,
        username=user.username,
        password_hash=hashed_password,
        role=user.role,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> schemas.Token:
    """
    Login user dengan username dan password, return JWT access token.
    
    - Cek username ada di database
    - Verifikasi password dengan bcrypt hash
    - Generate JWT token dengan claims: sub (username), role, exp
    - Token bisa digunakan untuk authorized endpoint dengan header "Authorization: Bearer {token}"
    
    Args:
        form_data: OAuth2PasswordRequestForm (username + password dari form body)
        db: Database session
    
    Returns:
        Token schema dengan access_token dan token_type="bearer"
    
    Raises:
        401: Username atau password salah
    """
    # Query user dari database
    user = db.query(models.UserAccount).filter(
        models.UserAccount.username == form_data.username
    ).first()
    
    # Validasi: user harus ada dan password harus cocok
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last_login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Buat JWT token dengan claims
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": user.username,
        "role": user.role,
        "user_id": user.user_id
    }
    access_token = create_access_token(
        data=to_encode,
        expires_delta=access_token_expires
    )
    
    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        username=user.username
    )