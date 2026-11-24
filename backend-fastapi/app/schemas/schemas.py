from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.models import UserRole, KYCStatus, ShiftStatus, PaymentStatus

class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.WORKER
    phone: Optional[str] = None
    payout_upi_id: Optional[str] = "worker@okhdfcbank"

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: UserRole
    name: str

class PANVerificationRequest(BaseModel):
    pan_number: str = Field(
        ...,
        min_length=10,
        max_length=10,
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
        json_schema_extra={"example": "ABCPE1234F"}
    )
    document_url: str = Field(..., json_schema_extra={"example": "https://storage.hstaff.com/kyc/pan.jpg"})

class KYCReviewRequest(BaseModel):
    action: KYCStatus
    remarks: Optional[str] = None

class ClockInRequest(BaseModel):
    assignment_id: str
    signed_qr_token: str
    latitude: float
    longitude: float
    selfie_image_url: Optional[str] = None

class ClockOutRequest(BaseModel):
    assignment_id: str
    signed_qr_token: Optional[str] = None
    latitude: float
    longitude: float
    customer_completion_otp: str = Field(..., min_length=4, max_length=6)

class CreateCheckoutOrderRequest(BaseModel):
    shift_id: str
    total_amount: float = Field(..., gt=0)

class VerifyWebhookRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class ExecutePayoutRequest(BaseModel):
    payout_account: Optional[str] = "worker@okhdfcbank"
    notes: Optional[str] = "Disbursement for verified hours"

class RaiseDisputeRequest(BaseModel):
    reason: str = Field(..., min_length=5)

class AdminDashboardStats(BaseModel):
    total_users: int
    active_workers: int
    active_shifts: int
    pending_kyc: int
    total_spend: float
    security_threats_blocked: int = 14

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: str
    actor_id: Optional[str]
    actor_role: Optional[str]
    action: str
    target_resource: str
    details: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime