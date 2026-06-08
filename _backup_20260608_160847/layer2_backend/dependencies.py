"""
dependencies.py
FastAPI dependency injection untuk JWT authentication dan role-based access control.
Semua router yang memerlukan auth harus import dari sini.
"""

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Callable, Optional

from . import models, database, config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db():
    """Dependency generator untuk database session. Selalu close setelah request."""
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.UserAccount:
    """
    Decode JWT token, validasi, return UserAccount dari DB.
    Raise HTTP 401 jika token invalid, expired, atau user tidak ditemukan.
    Error format: {"error": true, "code": "INVALID_TOKEN", "message": "..."}
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": True, "code": "INVALID_TOKEN", "message": "Token tidak valid atau sudah expired."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.UserAccount).filter(
        models.UserAccount.username == username
    ).first()
    if user is None:
        raise credentials_exception
    return user


def require_role(*allowed_roles: str) -> Callable:
    """
    Factory function: return dependency yang cek role user.

    Cara pakai:
        @router.get("/endpoint")
        def endpoint(current_user = Depends(require_role("admin", "supervisor"))):
            ...

    Raise HTTP 403 jika role user tidak ada di allowed_roles.
    Error format: {"error": true, "code": "FORBIDDEN", "message": "..."}
    """
    def role_checker(
        current_user: models.UserAccount = Depends(get_current_user)
    ) -> models.UserAccount:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": True,
                    "code": "FORBIDDEN",
                    "message": f"Akses ditolak. Role yang diizinkan: {', '.join(allowed_roles)}."
                }
            )
        return current_user
    return role_checker


def get_any_authenticated_user(
    current_user: models.UserAccount = Depends(get_current_user)
) -> models.UserAccount:
    """Shortcut: semua role yang sudah login boleh akses."""
    return current_user


def verify_internal_key(x_internal_key: Optional[str] = Header(default=None)) -> bool:
    """
    Validasi X-Internal-Key header untuk endpoint internal (CV module).
    Raise HTTP 401 jika key salah atau tidak ada.
    """
    if x_internal_key != config.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": True, "code": "INVALID_KEY", "message": "Internal API key tidak valid."}
        )
    return True
