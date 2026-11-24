from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import RequireRole, get_current_user
from app.models.models import Payment, PaymentStatus, WorkerProfile, User, Shift
from app.schemas.schemas import (
    CreateCheckoutOrderRequest, VerifyWebhookRequest,
    ExecutePayoutRequest, RaiseDisputeRequest
)
from app.services.payment_gateway_service import payment_engine
from app.services.audit_service import AuditLogger

router = APIRouter(prefix="/payments", tags=["Payment & Escrow Engine"])
require_admin = RequireRole(["admin"])
require_business = RequireRole(["business", "admin"])

@router.get("/overview")
def get_payments_overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    payments = db.query(Payment, WorkerProfile, User, Shift)\
        .join(WorkerProfile, Payment.worker_id == WorkerProfile.worker_id)\
        .join(User, WorkerProfile.user_id == User.user_id)\
        .join(Shift, Payment.shift_id == Shift.shift_id)\
        .order_by(Payment.created_at.desc())\
        .all()

    total_disbursed = sum(float(p.Payment.net_worker_payout or p.Payment.amount) for p in payments if p.Payment.status == PaymentStatus.PAID)
    total_in_escrow = sum(float(p.Payment.net_worker_payout or p.Payment.amount) for p in payments if p.Payment.status in [PaymentStatus.PENDING, PaymentStatus.ESCROW_HOLD])
    total_platform_revenue = sum(float(p.Payment.platform_commission or 0) for p in payments if p.Payment.status == PaymentStatus.PAID)

    records = []
    for item in payments:
        records.append({
            "payment_id": item.Payment.payment_id,
            "worker_name": item.User.name,
            "worker_phone": item.WorkerProfile.phone,
            "worker_payout_account": item.WorkerProfile.payout_upi_id or "worker@okhdfcbank",
            "shift_title": item.Shift.title,
            "hours_worked": float(item.Payment.hours_worked),
            "hourly_rate": float(item.Payment.hourly_rate),
            "surge_multiplier": float(item.Payment.surge_multiplier or 1.0),
            "gross_amount": float(item.Payment.gross_amount or item.Payment.amount),
            "platform_commission_15pct": float(item.Payment.platform_commission or 0),
            "gst_on_commission_18pct": float(item.Payment.gst_on_commission or 0),
            "tds_deduction_1pct": float(item.Payment.tds_deduction or 0),
            "kit_tool_deduction": float(item.Payment.kit_tool_deduction or 0),
            "net_worker_payout": float(item.Payment.net_worker_payout or item.Payment.amount),
            "gst_invoice_number": item.Payment.gst_invoice_number or "HST-INV-2026-N/A",
            "sac_code": "9987 (Staffing & Support Services)",
            "status": item.Payment.status.value,
            "gateway_ref": item.Payment.gateway_reference or "N/A",
            "created_at": item.Payment.created_at.strftime("%d %b %Y, %I:%M %p"),
            "paid_at": item.Payment.paid_at.strftime("%d %b %Y, %I:%M %p") if item.Payment.paid_at else "Pending Release"
        })

    return {
        "metrics": {
            "total_disbursed": round(total_disbursed, 2),
            "total_in_escrow": round(total_in_escrow, 2),
            "total_platform_revenue": round(total_platform_revenue, 2),
            "transaction_count": len(records)
        },
        "transactions": records
    }

@router.post("/checkout/create-order")
def create_checkout_order(
    payload: CreateCheckoutOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_business)
):
    shift = db.query(Shift).filter(Shift.shift_id == payload.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    order_details = payment_engine.create_escrow_order(
        amount=payload.total_amount,
        receipt_id=f"shf_{shift.shift_id[:8]}"
    )
    return {
        "status": "success",
        "message": "H-Staff Escrow Order created.",
        "order": order_details
    }

@router.post("/webhook/verify")
async def verify_gateway_webhook(
    request: Request,
    payload: VerifyWebhookRequest,
    db: Session = Depends(get_db)
):
    body_raw = (await request.body()).decode()
    signature = request.headers.get("X-Razorpay-Signature", payload.razorpay_signature)

    is_valid = payment_engine.verify_webhook_signature(body_raw, signature)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid HMAC cryptographic signature.")

    return {"status": "verified", "payment_id": payload.razorpay_payment_id}

@router.post("/{payment_id}/release-payout")
def release_worker_payout(
    payment_id: str,
    payload: ExecutePayoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if payment.status == PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Payout has already been settled for this timesheet")

    transfer_amount = float(payment.net_worker_payout or payment.amount)

    payout_result = payment_engine.execute_instant_payout(
        worker_upi_or_bank=payload.payout_account,
        amount=transfer_amount,
        narration=payload.notes or f"H-Staff Payout for Invoice {payment.gst_invoice_number}"
    )

    payment.status = PaymentStatus.PAID
    payment.gateway_reference = payout_result["bank_rrn"]
    payment.paid_at = datetime.now(timezone.utc)
    db.commit()

    AuditLogger.write(
        db, admin.user_id, admin.role.value, "WORKER_PAYOUT_SETTLED",
        f"payment:{payment_id}",
        details=f"Disbursed Net ₹{transfer_amount} (Invoice: {payment.gst_invoice_number}) via RRN {payout_result['bank_rrn']}",
        request=request
    )

    return {
        "status": "success",
        "message": "Worker payout settled successfully with H-Staff tax compliance.",
        "gateway_response": payout_result
    }

@router.post("/{payment_id}/dispute")
def dispute_timesheet_payout(
    payment_id: str,
    payload: RaiseDisputeRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    payment.status = PaymentStatus.DISPUTED
    payment.dispute_reason = payload.reason
    db.commit()

    AuditLogger.write(
        db, admin.user_id, admin.role.value, "PAYOUT_DISPUTED",
        f"payment:{payment_id}",
        details=f"Under 24-hr SLA review. Reason: {payload.reason}",
        request=request
    )

    return {"status": "success", "message": "Payout moved to Escrow dispute hold."}
