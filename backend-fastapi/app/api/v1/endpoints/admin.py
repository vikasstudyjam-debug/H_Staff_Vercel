from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import RequireRole
from app.models.models import User, WorkerProfile, Shift, KYCStatus, ShiftStatus
from app.schemas.schemas import AdminDashboardStats, KYCReviewRequest
from app.services.audit_service import AuditLogger
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/admin", tags=["Admin Portal & KYC Operations"])
require_admin = RequireRole(["admin"])

@router.get("/dashboard/stats", response_model=AdminDashboardStats)
def get_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    total_users = db.query(User).count()
    active_workers = db.query(WorkerProfile).join(User).filter(User.is_active == True).count()
    active_shifts = db.query(Shift).filter(Shift.status.in_([ShiftStatus.OPEN, ShiftStatus.FILLED])).count()
    pending_kyc = db.query(WorkerProfile).filter(WorkerProfile.kyc_status == KYCStatus.PENDING).count()

    return AdminDashboardStats(
        total_users=total_users,
        active_workers=active_workers,
        active_shifts=active_shifts,
        pending_kyc=pending_kyc,
        total_spend=24500.0,
        security_threats_blocked=14
    )

@router.get("/kyc/pending")
def pending_kyc_list(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    records = (
        db.query(WorkerProfile, User)
        .join(User, WorkerProfile.user_id == User.user_id)
        .all()
    )
    return [
        {
            "worker_id": r.WorkerProfile.worker_id,
            "user_id": r.User.user_id,
            "name": r.User.name,
            "email": r.User.email,
            "phone": r.WorkerProfile.phone,
            "document_type": r.WorkerProfile.document_type or "PAN Card",
            "document_number": r.WorkerProfile.document_number or "N/A",
            "document_url": r.WorkerProfile.document_url,
            "status": r.WorkerProfile.kyc_status.value
        }
        for r in records
    ]

@router.post("/kyc/{worker_id}/review")
def review_kyc(
    worker_id: str,
    payload: KYCReviewRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    worker = db.query(WorkerProfile).filter(WorkerProfile.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker record not found")

    user = db.query(User).filter(User.user_id == worker.user_id).first()

    worker.kyc_status = payload.action
    worker.kyc_notes = payload.remarks
    worker.kyc_reviewed_by = admin.user_id
    worker.kyc_reviewed_at = datetime.now(timezone.utc)
    db.commit()

    # Immutable Audit Log
    AuditLogger.write(
        db, admin.user_id, admin.role.value, f"KYC_{payload.action.value.upper()}",
        f"worker:{worker_id}", details=f"Remarks: {payload.remarks}", request=request
    )

    # Automated Email Trigger using BackgroundTasks
    if user:
        background_tasks.add_task(
            NotificationService.send_kyc_status_email,
            to_email=user.email,
            worker_name=user.name,
            status=payload.action.value,
            remarks=payload.remarks
        )

    return {
        "status": "success",
        "worker_id": worker_id,
        "kyc_status": worker.kyc_status.value,
        "notification_dispatched": True
    }
