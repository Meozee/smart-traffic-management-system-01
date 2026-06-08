"""
dependencies.py
FastAPI dependency injection untuk JWT authentication dan role-based access control.
Semua router yang memerlukan auth harus import dari sini.
"""

from fastapi import (
    Depends,
    HTTPException,
    status,
    Header,
    Query,
)
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Callable, Optional

from . import models, database, config


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


def get_db():
    """
    Dependency generator untuk database session.
    Selalu close setelah request.
    """
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.UserAccount:
    """
    Decode JWT token, validasi, return UserAccount dari DB.

    Raise HTTP 401 jika token invalid,
    expired, atau user tidak ditemukan.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": True,
            "code": "INVALID_TOKEN",
            "message": "Token tidak valid atau sudah expired.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM],
        )

        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(models.UserAccount)
        .filter(models.UserAccount.username == username)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


def require_role(*allowed_roles: str) -> Callable:
    """
    Factory function untuk validasi role.

    Contoh:

        @router.get("/endpoint")
        def endpoint(
            current_user=Depends(
                require_role("admin", "supervisor")
            )
        ):
            ...
    """

    def role_checker(
        current_user: models.UserAccount = Depends(
            get_current_user
        )
    ) -> models.UserAccount:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": True,
                    "code": "FORBIDDEN",
                    "message":
                        f"Akses ditolak. Role yang diizinkan: "
                        f"{', '.join(allowed_roles)}."
                },
            )

        return current_user

    return role_checker


def get_any_authenticated_user(
    current_user: models.UserAccount = Depends(
        get_current_user
    ),
) -> models.UserAccount:
    """
    Shortcut:
    Semua user yang sudah login boleh akses.
    """
    return current_user


def get_stream_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> models.UserAccount:
    """
    Dependency khusus endpoint streaming MJPEG.

    Sumber token:
      1. Authorization: Bearer xxx
      2. ?token=xxx

    Prioritas:
      Header Authorization > Query String
    """

    raw_token = None

    # Authorization header
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1]

    # Query parameter
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": True,
                "code": "INVALID_TOKEN",
                "message": "Token tidak ditemukan.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": True,
            "code": "INVALID_TOKEN",
            "message": "Token tidak valid atau sudah expired.",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            raw_token,
            config.SECRET_KEY,
            algorithms=[config.ALGORITHM],
        )

        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(models.UserAccount)
        .filter(models.UserAccount.username == username)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


def verify_internal_key(
    x_internal_key: Optional[str] = Header(default=None),
) -> bool:
    """
    Validasi X-Internal-Key untuk endpoint internal.
    """

    if x_internal_key != config.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": True,
                "code": "INVALID_KEY",
                "message": "Internal API key tidak valid.",
            },
        )

    return True