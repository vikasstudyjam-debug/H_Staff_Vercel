import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column, String, Boolean, DateTime, Enum as SQLEnum,
    ForeignKey, Numeric, Text, Integer, Float
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    BUSINESS = "business"
    WORKER = "worker"

class KYCStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class BGCStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FLAGGED = "flagged"

class ShiftStatus(str, enum.Enum):
    OPEN = "open"
    FILLED = "filled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class AssignmentStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    ESCROW_HOLD = "escrow_hold"
    PROCESSING = "processing"
    PAID = "paid"
    DISPUTED = "disputed"
    REFUNDED = "refunded"

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.WORKER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    worker = relationship("WorkerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="actor")

class WorkerProfile(Base):
    __tablename__ = "workers"

    worker_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), unique=True, nullable=False)
    phone = Column(String(20), nullable=True)
    payout_upi_id = Column(String(100), nullable=True, default="worker@okhdfcbank")
    kyc_status = Column(SQLEnum(KYCStatus), default=KYCStatus.PENDING, nullable=False)
    
    # H-Staff Enterprise Partner Verification & Trust Badges
    bgc_status = Column(SQLEnum(BGCStatus), default=BGCStatus.PENDING, nullable=False)
    is_trusted_badge = Column(Boolean, default=False)
    police_verification_ref = Column(String(100), nullable=True)
    
    # H-Staff Partner Virtual Wallet & Kit Amortization
    wallet_balance = Column(Numeric(10, 2), default=0.0)
    security_deposit_balance = Column(Numeric(10, 2), default=1500.0)
    
    document_type = Column(String(50), nullable=True)
    document_number = Column(String(50), nullable=True)
    document_url = Column(String(500), nullable=True)
    kyc_notes = Column(Text, nullable=True)
    kyc_reviewed_by = Column(String(36), nullable=True)
    kyc_reviewed_at = Column(DateTime, nullable=True)
    rating_avg = Column(Numeric(3, 2), default=5.0)

    user = relationship("User", back_populates="worker")
    assignments = relationship("Assignment", back_populates="worker")
    payouts = relationship("Payment", back_populates="worker")

class Shift(Base):
    __tablename__ = "shifts"

    shift_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String(36), nullable=False)
    title = Column(String(150), nullable=False)
    location_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geofence_radius_meters = Column(Float, default=200.0)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    capacity_required = Column(Integer, default=1)
    hourly_rate = Column(Numeric(10, 2), nullable=False)
    
    # H-Staff Dynamic Demand Surge Multiplier
    surge_multiplier = Column(Float, default=1.0)
    
    status = Column(SQLEnum(ShiftStatus), default=ShiftStatus.OPEN, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assignments = relationship("Assignment", back_populates="shift", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="shift")

class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shift_id = Column(String(36), ForeignKey("shifts.shift_id"), nullable=False)
    worker_id = Column(String(36), ForeignKey("workers.worker_id"), nullable=False)
    status = Column(SQLEnum(AssignmentStatus), default=AssignmentStatus.ASSIGNED, nullable=False)
    
    # H-Staff Secure Customer Handshake Completion OTP
    customer_completion_otp = Column(String(6), nullable=True, default="7429")
    otp_verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    shift = relationship("Shift", back_populates="assignments")
    worker = relationship("WorkerProfile", back_populates="assignments")
    attendance = relationship("Attendance", back_populates="assignment", uselist=False, cascade="all, delete-orphan")

ShiftAssignment = Assignment

class Attendance(Base):
    __tablename__ = "attendance"

    attendance_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id = Column(String(36), ForeignKey("assignments.assignment_id"), unique=True, nullable=False)
    clock_in = Column(DateTime, nullable=True)
    clock_out = Column(DateTime, nullable=True)
    clock_in_latitude = Column(Float, nullable=True)
    clock_in_longitude = Column(Float, nullable=True)
    clock_out_latitude = Column(Float, nullable=True)
    clock_out_longitude = Column(Float, nullable=True)
    clock_in_distance_meters = Column(Float, nullable=True)
    clock_out_distance_meters = Column(Float, nullable=True)
    
    # H-Staff Biometric Onsite Selfie & Liveness Verification
    selfie_image_url = Column(String(500), nullable=True)
    liveness_verified = Column(Boolean, default=False)
    
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assignment = relationship("Assignment", back_populates="attendance")

class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    worker_id = Column(String(36), ForeignKey("workers.worker_id"), nullable=False)
    shift_id = Column(String(36), ForeignKey("shifts.shift_id"), nullable=False)
    
    # H-Staff Split Settlement Engine Breakdown
    hours_worked = Column(Numeric(6, 2), default=8.0)
    hourly_rate = Column(Numeric(10, 2), nullable=False)
    surge_multiplier = Column(Float, default=1.0)
    gross_amount = Column(Numeric(10, 2), nullable=False)
    platform_commission = Column(Numeric(10, 2), default=0.0)      # H-Staff Take-rate (15%)
    gst_on_commission = Column(Numeric(10, 2), default=0.0)        # 18% GST on Commission
    tds_deduction = Column(Numeric(10, 2), default=0.0)            # 1% Section 194-O TDS
    kit_tool_deduction = Column(Numeric(10, 2), default=0.0)       # Kit amortized deduction
    net_worker_payout = Column(Numeric(10, 2), nullable=False)       # Net Disbursed Amount
    amount = Column(Numeric(10, 2), nullable=False)                # Net/Payable total
    
    # H-Staff Regulatory B2B Invoicing
    gst_invoice_number = Column(String(50), nullable=True)         # HST-INV-2026-XXXX (SAC: 9987)
    
    gateway_order_id = Column(String(100), nullable=True)
    gateway_reference = Column(String(100), nullable=True)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    dispute_reason = Column(Text, nullable=True)
    sla_deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime, nullable=True)

    worker = relationship("WorkerProfile", back_populates="payouts")
    shift = relationship("Shift", back_populates="payments")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    actor_role = Column(String(20), nullable=True)
    action = Column(String(100), nullable=False)
    target_resource = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    actor = relationship("User", back_populates="audit_logs")
