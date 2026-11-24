from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import RequireRole, get_current_user
from app.models.models import User, WorkerProfile, KYCStatus, UserRole
from app.services.kyc_service import document_kyc_service
from app.services.audit_service import AuditLogger

router = APIRouter(prefix="/worker", tags=["Worker Profile & Document KYC"])
require_worker = RequireRole(["worker"])

@router.post("/kyc/upload-document")
async def upload_kyc_document(
    file: UploadFile = File(...),
    document_type: str = Form("Government Identity Document"),
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_worker)
):
    profile = db.query(WorkerProfile).filter(WorkerProfile.user_id == user.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Worker profile not found")
    
    saved = await document_kyc_service.save_kyc_document(file, document_label=document_type)
    
    profile.document_type = saved["document_type"]
    profile.document_number = saved["secure_filename"]
    profile.document_url = f"/api/v1/worker/kyc/{profile.worker_id}/file"
    profile.kyc_status = KYCStatus.PENDING
    db.commit()

    AuditLogger.write(
        db, user.user_id, user.role.value, "KYC_DOCUMENT_UPLOADED",
        f"worker:{profile.worker_id}",
        details=f"Uploaded {saved['document_type']} securely as {saved['secure_filename']}",
        request=request
    )

    return {
        "status": "success",
        "message": "KYC document uploaded privately. Pending admin review.",
        "worker_id": profile.worker_id,
        "kyc_status": profile.kyc_status.value,
        "document_url": profile.document_url
    }

@router.get("/kyc/{worker_id}/file")
def stream_kyc_document(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    profile = db.query(WorkerProfile).filter(WorkerProfile.worker_id == worker_id).first()
    if not profile or not profile.document_number:
        raise HTTPException(status_code=404, detail="KYC document record not found")

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = current_user.role == UserRole.WORKER and profile.user_id == current_user.user_id
    if not (is_admin or is_owner):
        raise HTTPException(status_code=403, detail="Access denied: Only document owner or admin can view KYC files")

    file_path = document_kyc_service.get_document_path(profile.document_number)
    return FileResponse(path=str(file_path), filename=profile.document_number)
