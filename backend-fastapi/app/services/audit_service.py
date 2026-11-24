import uuid
from datetime import datetime, timezone
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.models import AuditLog

class AuditLogger:
    @staticmethod
    def write(db: Session, actor_id: str, actor_role: str, action: str, target: str, details: str = None, request: Request = None):
        ip = request.client.host if request and request.client else None
        entry = AuditLog(
            log_id=str(uuid.uuid4()),
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            target_resource=target,
            details=details,
            ip_address=ip,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(entry)
        db.commit()
