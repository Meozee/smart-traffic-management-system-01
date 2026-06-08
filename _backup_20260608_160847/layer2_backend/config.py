"""
Smart Traffic Monitoring System (STMS) — Configuration Module

This module loads all application configuration from environment variables
(from .env file at project root). All hardcoded values should be moved here
and accessed by other modules.

All timestamp operations use UTC timezone consistently.
"""

import os
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════════════════════
# LOAD ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════

# Load .env file from parent directory (project root)
# Path resolution: layer2_backend/config.py → go up one level for .env
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path, verbose=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://stms_user:stms_password@localhost:5432/stms_db"
)
"""PostgreSQL connection string. Format: postgresql://user:password@host:port/db"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY & AUTHENTICATION CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SECRET_KEY: str = os.getenv(
    "SECRET_KEY",
    "CHANGE_THIS_IN_PRODUCTION_NOT_FOR_ACTUAL_USE"
)
"""Secret key untuk JWT token generation. HARUS diganti di production."""

ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
"""Algorithm untuk JWT token encoding/decoding."""

ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
"""JWT token expiration time dalam menit (default: 8 jam)."""


# ═══════════════════════════════════════════════════════════════════════════════
# YOLOV8 & COMPUTER VISION CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MODEL_PATH: str = os.getenv("MODEL_PATH", "yolov8n.pt")
"""Path ke YOLOv8 model weights file (.pt)."""

CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
"""Minimum confidence score untuk detection hasil YOLO (0.0-1.0)."""


# ═══════════════════════════════════════════════════════════════════════════════
# TRAFFIC DENSITY THRESHOLDS (DEFAULT FALLBACKS)
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_DENSITY_LOW_PERCENT: float = float(os.getenv("DENSITY_LOW_THRESHOLD", "40"))
_DEFAULT_DENSITY_HIGH_PERCENT: float = float(os.getenv("DENSITY_HIGH_THRESHOLD", "70"))

DEFAULT_DENSITY_LOW: float = _DEFAULT_DENSITY_LOW_PERCENT / 100.0
"""
DEFAULT Threshold untuk density level 'Low' (dalam ratio 0.0-1.0).
Digunakan sebagai nilai awal saat admin mendaftarkan kamera baru.
"""

DEFAULT_DENSITY_HIGH: float = _DEFAULT_DENSITY_HIGH_PERCENT / 100.0
"""
DEFAULT Threshold untuk density level 'High' (dalam ratio 0.0-1.0).
Digunakan sebagai nilai awal saat admin mendaftarkan kamera baru.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DENSITY_INTERVAL_MINUTES: int = int(os.getenv("DENSITY_INTERVAL_MINUTES", "15"))
"""
Interval (dalam menit) untuk menjalankan background job kalkulasi traffic density.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# FRONTEND DASHBOARD CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DASHBOARD_POLL_INTERVAL_MS: int = int(os.getenv("DASHBOARD_POLL_INTERVAL_MS", "5000"))
"""
Interval polling (dalam milliseconds) untuk dashboard frontend.
Frontend akan melakukan fetch API setiap interval ini untuk update real-time.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# CORS CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

_ALLOWED_ORIGINS_STR: str = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost,http://127.0.0.1"
)

ALLOWED_ORIGINS: list = [origin.strip() for origin in _ALLOWED_ORIGINS_STR.split(",")]
"""
List of CORS-allowed origins untuk cross-origin requests dari frontend.
Diparsing dari ALLOWED_ORIGINS env var (comma-separated).
"""


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL API KEY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "stms-internal-key-2025")
"""
Internal API key untuk komunikasi CV module (layer1) ke backend (layer2).
Disertakan di header X-Internal-Key pada endpoint internal.
Gunakan nilai acak yang kuat di production.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION & SANITY CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

def validate_config() -> None:
    """
    Validate critical configuration values pada startup.
    Raise exception jika ada value yang invalid.
    """
    errors = []

    if not DATABASE_URL or "postgresql://" not in DATABASE_URL:
        errors.append(
            "❌ DATABASE_URL invalid atau tidak dikonfigurasi. "
            "Periksa .env file atau environment variable."
        )

    if SECRET_KEY == "CHANGE_THIS_IN_PRODUCTION_NOT_FOR_ACTUAL_USE":
        errors.append(
            "⚠️  WARNING: SECRET_KEY masih menggunakan nilai default. "
            "HARUS diganti dengan random string di production."
        )

    if not (0.0 <= CONFIDENCE_THRESHOLD <= 1.0):
        errors.append(
            f"❌ CONFIDENCE_THRESHOLD harus 0.0-1.0, ditemukan: {CONFIDENCE_THRESHOLD}"
        )

    # FIXED: Menggunakan variabel DEFAULT yang baru
    if not (0.0 <= DEFAULT_DENSITY_LOW <= 1.0):
        errors.append(
            f"❌ DEFAULT_DENSITY_LOW harus 0.0-1.0, ditemukan: {DEFAULT_DENSITY_LOW}"
        )

    if not (0.0 <= DEFAULT_DENSITY_HIGH <= 1.0):
        errors.append(
            f"❌ DEFAULT_DENSITY_HIGH harus 0.0-1.0, ditemukan: {DEFAULT_DENSITY_HIGH}"
        )

    if DEFAULT_DENSITY_LOW >= DEFAULT_DENSITY_HIGH:
        errors.append(
            f"❌ DEFAULT_DENSITY_LOW ({DEFAULT_DENSITY_LOW}) harus < "
            f"DEFAULT_DENSITY_HIGH ({DEFAULT_DENSITY_HIGH})"
        )

    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        errors.append(
            f"❌ ACCESS_TOKEN_EXPIRE_MINUTES harus > 0, ditemukan: {ACCESS_TOKEN_EXPIRE_MINUTES}"
        )

    if DENSITY_INTERVAL_MINUTES <= 0:
        errors.append(
            f"❌ DENSITY_INTERVAL_MINUTES harus > 0, ditemukan: {DENSITY_INTERVAL_MINUTES}"
        )

    if DASHBOARD_POLL_INTERVAL_MS <= 0:
        errors.append(
            f"❌ DASHBOARD_POLL_INTERVAL_MS harus > 0, ditemukan: {DASHBOARD_POLL_INTERVAL_MS}"
        )

    if len(ALLOWED_ORIGINS) == 0:
        errors.append(
            "❌ ALLOWED_ORIGINS kosong. Periksa .env file."
        )

    if errors:
        error_message = "\n".join(errors)
        raise ValueError(f"Configuration validation failed:\n{error_message}")

    print("✅ Configuration validation passed.")


# ═══════════════════════════════════════════════════════════════════════════════
# DEBUG INFO (only in development)
# ═══════════════════════════════════════════════════════════════════════════════

def print_config_summary() -> None:
    """Print configuration summary untuk debugging (non-sensitive values only)."""
    print("\n" + "═" * 80)
    print("STMS CONFIGURATION SUMMARY")
    print("═" * 80)
    print(f"✓ DATABASE_URL: {DATABASE_URL.replace('stms_password', '***')}")
    print(f"✓ ALGORITHM: {ALGORITHM}")
    print(f"✓ ACCESS_TOKEN_EXPIRE_MINUTES: {ACCESS_TOKEN_EXPIRE_MINUTES}")
    print(f"✓ CONFIDENCE_THRESHOLD: {CONFIDENCE_THRESHOLD}")
    # FIXED: Menyesuaikan penamaan di console log
    print(f"✓ DEFAULT_DENSITY_LOW: {DEFAULT_DENSITY_LOW:.2%}")
    print(f"✓ DEFAULT_DENSITY_HIGH: {DEFAULT_DENSITY_HIGH:.2%}")
    print(f"✓ DENSITY_INTERVAL_MINUTES: {DENSITY_INTERVAL_MINUTES}")
    print(f"✓ DASHBOARD_POLL_INTERVAL_MS: {DASHBOARD_POLL_INTERVAL_MS}")
    print(f"✓ ALLOWED_ORIGINS: {', '.join(ALLOWED_ORIGINS)}")
    print(f"✓ INTERNAL_API_KEY: {'*' * len(INTERNAL_API_KEY)}  (hidden)")
    print("═" * 80 + "\n")


if __name__ == "__main__":
    validate_config()
    print_config_summary()