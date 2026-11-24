from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.core.security import RequireRole
from app.models.models import AuditLog, User
from app.schemas.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit & Security"])
require_admin = RequireRole(["admin"])

@router.get("/logs", response_model=List[AuditLogResponse])
def get_logs(action: Optional[str] = Query(None), db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.order_by(desc(AuditLog.timestamp)).limit(100).all()
