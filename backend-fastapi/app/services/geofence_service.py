import math
import hmac
import hashlib
import time
from datetime import datetime, timezone
from typing import Tuple
from app.core.config import settings

class GeofenceVerificationService:
    """
    Haversine Geospatial Geofence Calculation Engine (<= 200m).
    Includes Anti-GPS Spoofing via Impossible Travel Speed Checks and Signed QR Codes.
    """
    @staticmethod
    def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates great-circle distance between two GPS coordinates in meters.
        """
        R = 6371000.0  # Earth's radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    @classmethod
    def check_impossible_travel(
        cls,
        lat1: float, lon1: float, time1: datetime,
        lat2: float, lon2: float, time2: datetime,
        max_speed_kmh: float = 120.0
    ) -> Tuple[bool, float]:
        """
        Detects Mock Location / Teleportation fraud by calculating velocity between two logs.
        Returns (is_fraudulent, speed_kmh).
        """
        distance_meters = cls.calculate_haversine_distance(lat1, lon1, lat2, lon2)
        time_diff_seconds = abs((time2 - time1).total_seconds())

        if time_diff_seconds < 1.0:
            return (distance_meters > 100.0, 999.0)

        speed_mps = distance_meters / time_diff_seconds
        speed_kmh = speed_mps * 3.6

        is_fraud = speed_kmh > max_speed_kmh
        return (is_fraud, round(speed_kmh, 2))

    @staticmethod
    def generate_signed_qr_token(shift_id: str, business_id: str, ttl_seconds: int = 300) -> str:
        expires_at = int(time.time()) + ttl_seconds
        payload = f"{shift_id}:{business_id}:{expires_at}"
        signature = hmac.new(
            settings.QR_HMAC_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return f"{shift_id}:{expires_at}:{signature}"

    @staticmethod
    def verify_signed_qr_token(shift_id: str, business_id: str, token: str) -> bool:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        token_shift_id, str_expires_at, provided_sig = parts
        if token_shift_id != shift_id:
            return False

        try:
            expires_at = int(str_expires_at)
        except ValueError:
            return False

        if time.time() > expires_at:
            return False

        payload = f"{shift_id}:{business_id}:{expires_at}"
        expected_sig = hmac.new(
            settings.QR_HMAC_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(expected_sig, provided_sig)
