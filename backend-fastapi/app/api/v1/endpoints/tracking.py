from datetime import datetime, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.core.security import RequireRole
from app.models.models import (
    Shift, ShiftAssignment, Attendance, ShiftStatus,
    AssignmentStatus, User, WorkerProfile, Payment, PaymentStatus
)
from app.schemas.schemas import ClockInRequest, ClockOutRequest
from app.services.geofence_service import GeofenceVerificationService
from app.services.payment_gateway_service import payment_engine
from app.services.audit_service import AuditLogger

router = APIRouter(prefix="/tracking", tags=["Shifts, Geofence & Attendance"])
require_admin_or_business = RequireRole(["admin", "business"])
require_worker = RequireRole(["worker"])

@router.get("/shifts")
def list_monitored_shifts(
    status: Optional[ShiftStatus] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_business)
):
    q = db.query(Shift)
    if status:
        q = q.filter(Shift.status == status)
    return q.order_by(desc(Shift.created_at)).all()

@router.get("/shifts/{shift_id}/qr-token")
def generate_shift_qr_token(
    shift_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_or_business)
):
    shift = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    token = GeofenceVerificationService.generate_signed_qr_token(
        shift_id=shift.shift_id,
        business_id=shift.business_id
    )
    return {
        "shift_id": shift_id,
        "signed_qr_token": token,
        "validity_seconds": 300,
        "location": {"latitude": shift.latitude, "longitude": shift.longitude}
    }

@router.post("/attendance/clock-in")
def process_geofenced_clock_in(
    payload: ClockInRequest,
    request: Request,
    db: Session = Depends(get_db),
    worker_user: User = Depends(require_worker)
):
    # 1. Fetch Worker Profile
    worker_profile = db.query(WorkerProfile).filter(WorkerProfile.user_id == worker_user.user_id).first()
    if not worker_profile:
        raise HTTPException(status_code=403, detail="Worker profile not configured.")

    # 2. Fetch Assignment
    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.assignment_id == payload.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Shift assignment not found")

    # 3. CRITICAL: Strict Assignment Ownership Verification (IDOR Defense)
    if assignment.worker_id != worker_profile.worker_id:
        raise HTTPException(status_code=403, detail="Ownership violation: You are not assigned to this shift.")

    # 4. Enforce State Transitions
    if assignment.status != AssignmentStatus.ASSIGNED:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition: Cannot clock in when assignment is {assignment.status.value}"
        )

    shift = assignment.shift

    # 5. Verify Signed QR Token
    is_qr_valid = GeofenceVerificationService.verify_signed_qr_token(
        shift_id=shift.shift_id,
        business_id=shift.business_id,
        token=payload.signed_qr_token
    )
    if not is_qr_valid:
        raise HTTPException(status_code=400, detail="QR code token has expired or signature is invalid.")

    # 6. Verify Geospatial Distance (<= 200m)
    distance_meters = GeofenceVerificationService.calculate_haversine_distance(
        payload.latitude, payload.longitude,
        shift.latitude, shift.longitude
    )
    if distance_meters > shift.geofence_radius_meters:
        raise HTTPException(
            status_code=403,
            detail=f"Geofence violation: Distance is {round(distance_meters, 1)}m. Site limit is {shift.geofence_radius_meters}m."
        )

    # 7. Record Attendance & Prevent Duplicate Events
    now = datetime.now(timezone.utc)
    selfie_url = getattr(payload, "selfie_image_url", None)

    attendance = db.query(Attendance).filter(Attendance.assignment_id == assignment.assignment_id).first()
    if not attendance:
        attendance = Attendance(
            assignment_id=assignment.assignment_id,
            clock_in=now,
            clock_in_latitude=payload.latitude,
            clock_in_longitude=payload.longitude,
            clock_in_distance_meters=round(distance_meters, 2),
            selfie_image_url=selfie_url,
            liveness_verified=bool(selfie_url),
            is_verified=True
        )
        db.add(attendance)
    else:
        if attendance.clock_in is not None:
            raise HTTPException(status_code=400, detail="Duplicate attendance: Clock-in already recorded.")
        attendance.clock_in = now
        attendance.clock_in_latitude = payload.latitude
        attendance.clock_in_longitude = payload.longitude
        attendance.clock_in_distance_meters = round(distance_meters, 2)
        attendance.selfie_image_url = selfie_url
        attendance.is_verified = True

    assignment.status = AssignmentStatus.IN_PROGRESS
    shift.status = ShiftStatus.IN_PROGRESS
    db.commit()

    AuditLogger.write(
        db, worker_user.user_id, worker_user.role.value, "ATTENDANCE_CLOCK_IN",
        f"assignment:{assignment.assignment_id}",
        details=f"Clock-in verified at distance {round(distance_meters, 1)}m",
        request=request
    )

    return {
        "status": "success",
        "message": "Clock-in verified.",
        "distance_meters": round(distance_meters, 1),
        "clock_in_time": attendance.clock_in
    }

@router.post("/attendance/clock-out")
def process_geofenced_clock_out(
    payload: ClockOutRequest,
    request: Request,
    db: Session = Depends(get_db),
    worker_user: User = Depends(require_worker)
):
    worker_profile = db.query(WorkerProfile).filter(WorkerProfile.user_id == worker_user.user_id).first()
    if not worker_profile:
        raise HTTPException(status_code=403, detail="Worker profile not configured.")

    assignment = db.query(ShiftAssignment).filter(ShiftAssignment.assignment_id == payload.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Shift assignment not found")

    # Strict Ownership Verification
    if assignment.worker_id != worker_profile.worker_id:
        raise HTTPException(status_code=403, detail="Ownership violation: You are not assigned to this shift.")

    if assignment.status != AssignmentStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition: Cannot clock out when assignment is {assignment.status.value}"
        )

    shift = assignment.shift

    # Verify Signed QR Token if provided
    qr_token = getattr(payload, "signed_qr_token", None)
    if qr_token:
        is_qr_valid = GeofenceVerificationService.verify_signed_qr_token(
            shift_id=shift.shift_id,
            business_id=shift.business_id,
            token=qr_token
        )
        if not is_qr_valid:
            raise HTTPException(status_code=400, detail="QR code token has expired or signature is invalid on clock-out.")

    # Customer Handshake OTP Verification
    if assignment.customer_completion_otp and payload.customer_completion_otp != assignment.customer_completion_otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Customer Completion OTP. Escrow payout cannot be authorized without client handshake."
        )

    # Geofence Distance Check
    distance_meters = GeofenceVerificationService.calculate_haversine_distance(
        payload.latitude, payload.longitude,
        shift.latitude, shift.longitude
    )
    if distance_meters > shift.geofence_radius_meters:
        raise HTTPException(
            status_code=403,
            detail=f"Geofence violation: Distance is {round(distance_meters, 1)}m. Must be within {shift.geofence_radius_meters}m to clock out."
        )

    attendance = db.query(Attendance).filter(Attendance.assignment_id == assignment.assignment_id).first()
    if not attendance or not attendance.clock_in:
        raise HTTPException(status_code=400, detail="Cannot clock out without prior verified clock-in.")

    if attendance.clock_out is not None:
        raise HTTPException(status_code=400, detail="Duplicate attendance: Clock-out already recorded.")

    now = datetime.now(timezone.utc)
    attendance.clock_out = now
    attendance.clock_out_latitude = payload.latitude
    attendance.clock_out_longitude = payload.longitude
    attendance.clock_out_distance_meters = round(distance_meters, 2)
    assignment.otp_verified_at = now

    # Automated Timesheet Calculation with Surge Multiplier
    duration_seconds = (attendance.clock_out - attendance.clock_in).total_seconds()
    hours_worked = max(round(duration_seconds / 3600.0, 2), 0.1)
    surge = shift.surge_multiplier or 1.0
    gross_amount = round(hours_worked * float(shift.hourly_rate) * surge, 2)

    # H-Staff Split Calculation
    split = payment_engine.calculate_hstaff_split(gross_amount, commission_percentage=15.0, amortize_kit=False)
    inv_num = f"HST-INV-2026-{uuid.uuid4().hex[:6].upper()}"

    assignment.status = AssignmentStatus.COMPLETED
    shift.status = ShiftStatus.COMPLETED

    payment = Payment(
        worker_id=assignment.worker_id,
        shift_id=shift.shift_id,
        hours_worked=hours_worked,
        hourly_rate=shift.hourly_rate,
        surge_multiplier=surge,
        gross_amount=gross_amount,
        platform_commission=split["platform_commission"],
        gst_on_commission=split["gst_on_commission"],
        tds_deduction=split["tds_deduction"],
        kit_tool_deduction=split["kit_tool_deduction"],
        net_worker_payout=split["net_worker_payout"],
        amount=split["net_worker_payout"],
        gst_invoice_number=inv_num,
        status=PaymentStatus.PENDING
    )
    db.add(payment)
    db.commit()

    AuditLogger.write(
        db, worker_user.user_id, worker_user.role.value, "ATTENDANCE_CLOCK_OUT",
        f"assignment:{assignment.assignment_id}",
        details=f"Customer OTP Authenticated. Net Wage: ₹{split['net_worker_payout']} | Tax Invoice: {inv_num}",
        request=request
    )

    return {
        "status": "success",
        "message": "Shift completed successfully.",
        "financial_breakdown": split,
        "gst_invoice_number": inv_num
    }