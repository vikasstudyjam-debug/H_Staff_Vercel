import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "H-Staff Enterprise Backend"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "production"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Security Secrets
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "9a7c3f81e2b4d6a8019c8f2b740e53a2d109f58204bca83120")
    JWT_REFRESH_SECRET_KEY: str = os.getenv("JWT_REFRESH_SECRET_KEY", "e83b102a94f6c8d10b73c2a9401f83c6129480aef891278")
    QR_HMAC_SECRET: str = os.getenv("QR_HMAC_SECRET", "qr_signing_secret_hstaff_geofence_2026_xyz")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # DB & Cache
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./hstaff_prod.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Razorpay Gateway Keys
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Verification Gateways
    PAN_GATEWAY_API_URL: str = os.getenv("PAN_GATEWAY_API_URL", "https://api.sandbox.co.in/kyc/pan")
    PAN_GATEWAY_API_KEY: str = os.getenv("PAN_GATEWAY_API_KEY", "")

    # Live SMTP Configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "compliance@hstaff.com")

    # Geofence & Constraints
    GEOFENCE_MAX_RADIUS_METERS: float = 200.0
    SLA_DISPUTE_WINDOW_HOURS: int = 24

settings = Settings()