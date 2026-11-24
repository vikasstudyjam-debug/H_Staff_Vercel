from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from datetime import datetime, timezone, timedelta
import os

from app.core.config import settings
from app.db.session import engine, Base, SessionLocal
from app.core.security import hash_password
from app.models.models import (
    User, WorkerProfile, Shift, UserRole, KYCStatus, BGCStatus,
    ShiftStatus, Payment, PaymentStatus, Assignment, AssignmentStatus, Attendance
)
from app.middlewares.waf import WebApplicationFirewallMiddleware
from app.api.v1.endpoints import auth, admin, tracking, audit, worker, payments

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        if not db.query(User).filter(User.email == "admin@hstaff.com").first():
            admin_user = User(
                user_id="usr_admin_001",
                name="H-Staff Operations Admin",
                email="admin@hstaff.com",
                password_hash=hash_password("admin_pass_2026"),
                role=UserRole.ADMIN,
                is_active=True
            )
            worker_user = User(
                user_id="usr_worker_001",
                name="Amit Sharma",
                email="amit@worker.com",
                password_hash=hash_password("worker_pass_2026"),
                role=UserRole.WORKER,
                is_active=True
            )
            worker_profile = WorkerProfile(
                worker_id="wrk_profile_001",
                user_id="usr_worker_001",
                phone="+91-9876543210",
                payout_upi_id="amit@okhdfcbank",
                kyc_status=KYCStatus.PENDING,
                bgc_status=BGCStatus.PENDING,
                is_trusted_badge=False,
                wallet_balance=0.0,
                security_deposit_balance=1500.0,
                document_type="PAN Card",
                document_number="ABCPE1234F",
                document_url="https://storage.hstaff.com/kyc/amit_pan.jpg"
            )
            worker_user2 = User(
                user_id="usr_worker_002",
                name="Rohit Kumar",
                email="rohit.k@worker.com",
                password_hash=hash_password("worker_pass_2026"),
                role=UserRole.WORKER,
                is_active=True
            )
            worker_profile2 = WorkerProfile(
                worker_id="wrk_profile_002",
                user_id="usr_worker_002",
                phone="+91-9876543211",
                payout_upi_id="rohit@okaxis",
                kyc_status=KYCStatus.APPROVED,
                bgc_status=BGCStatus.VERIFIED,
                is_trusted_badge=True,
                police_verification_ref="POL-MH-2026-9921",
                wallet_balance=1200.0,
                security_deposit_balance=0.0,
                document_type="PAN Card",
                document_number="BKWPR4321Q",
                document_url="https://storage.hstaff.com/kyc/rohit_pan.jpg"
            )

            # Start time aur End time correctly provided
            shift = Shift(
                shift_id="shf_001",
                business_id="usr_biz_001",
                title="Commercial Kitchen Helper",
                location_name="Mumbai, Andheri East",
                latitude=19.1197,
                longitude=72.8464,
                geofence_radius_meters=200.0,
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=10),
                capacity_required=5,
                hourly_rate=150.00,
                surge_multiplier=1.0,
                status=ShiftStatus.OPEN
            )
            shift2 = Shift(
                shift_id="shf_002",
                business_id="usr_biz_001",
                title="Warehouse Dispatch Rider",
                location_name="Mumbai, Bandra West",
                latitude=19.0596,
                longitude=72.8295,
                geofence_radius_meters=200.0,
                start_time=now - timedelta(hours=10),
                end_time=now - timedelta(hours=2),
                capacity_required=3,
                hourly_rate=180.00,
                surge_multiplier=1.2,
                status=ShiftStatus.FILLED
            )

            assignment = Assignment(
                assignment_id="asg_001",
                shift_id="shf_002",
                worker_id="wrk_profile_002",
                customer_completion_otp="7429",
                status=AssignmentStatus.COMPLETED
            )
            payout1 = Payment(
                payment_id="pay_001",
                worker_id="wrk_profile_002",
                shift_id="shf_002",
                hours_worked=8.0,
                hourly_rate=180.00,
                surge_multiplier=1.2,
                gross_amount=1728.00,
                platform_commission=259.20,
                gst_on_commission=46.66,
                tds_deduction=17.28,
                kit_tool_deduction=0.00,
                net_worker_payout=1404.86,
                amount=1404.86,
                gst_invoice_number="HST-INV-2026-99102A",
                status=PaymentStatus.PENDING
            )
            db.add_all([
                admin_user, worker_user, worker_profile, worker_user2, worker_profile2,
                shift, shift2, assignment, payout1
            ])
            db.commit()
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT in ["development", "testing", "local"]:
        seed_database()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="4.5.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(WebApplicationFirewallMiddleware, requests_limit=250, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(tracking.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)
app.include_router(worker.router, prefix=settings.API_V1_STR)
app.include_router(payments.router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Dashboard UI"])
def serve_dashboard():
    if os.path.exists("app/static/index.html"):
        return FileResponse("app/static/index.html")
    return {"message": "H-Staff Enterprise API Running"}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy", "platform": "H-Staff Enterprise Architecture"}