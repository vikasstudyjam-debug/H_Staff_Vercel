from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app, seed_database
from app.db.session import engine, Base, SessionLocal
from app.models.models import Assignment, AssignmentStatus
from app.services.geofence_service import GeofenceVerificationService
from app.services.payment_gateway_service import payment_engine
from app.core.token_blacklist import token_blacklist

def test_full_security_lifecycle():
    # 0. Clean isolated DB environment reset
    Base.metadata.drop_all(bind=engine)
    seed_database()

    # Worker 1 (Amit: wrk_profile_001) ke liye ek genuine assignment create karo
    db = SessionLocal()
    try:
        amit_assignment = Assignment(
            assignment_id="asg_amit_001",
            shift_id="shf_001",
            worker_id="wrk_profile_001",
            customer_completion_otp="558821",
            status=AssignmentStatus.ASSIGNED
        )
        db.add(amit_assignment)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        # 1. Admin Login & JWT Issuance
        admin_login = client.post("/api/v1/auth/login", data={"username": "admin@hstaff.com", "password": "admin_pass_2026"})
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        # 2. Worker 1 (Amit) Login & JWT Issuance
        worker_login = client.post("/api/v1/auth/login", data={"username": "amit@worker.com", "password": "worker_pass_2026"})
        assert worker_login.status_code == 200
        worker_token = worker_login.json()["access_token"]

        # 3. RBAC Barrier Test: Worker denied from admin console (403)
        denied = client.get("/api/v1/admin/dashboard/stats", headers={"Authorization": f"Bearer {worker_token}"})
        assert denied.status_code == 403

        # 4. WAF Attack Test: SQLi Blocked (403)
        sqli_block = client.get("/api/v1/audit/logs?action=UNION SELECT * FROM users--")
        assert sqli_block.status_code == 403
        assert sqli_block.json()["error"] == "WAF_BLOCKED"

        # 5. Token Revocation / Blacklist Test (Immediate session kill)
        token_blacklist.revoke_token(worker_token)
        revoked_attempt = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {worker_token}"})
        assert revoked_attempt.status_code == 401

        # 6. Fresh Worker Login after Revocation (JTI Isolation)
        worker_login_fresh = client.post("/api/v1/auth/login", data={"username": "amit@worker.com", "password": "worker_pass_2026"})
        assert worker_login_fresh.status_code == 200
        fresh_worker_token = worker_login_fresh.json()["access_token"]

        # 7. PAN Validation Engine: Valid Format + Individual 'P' Entity Check
        pan_resp = client.post(
            "/api/v1/worker/kyc/verify-pan",
            json={"pan_number": "ABCPE1234F", "document_url": "https://storage.hstaff.com/kyc/pan.jpg"},
            headers={"Authorization": f"Bearer {fresh_worker_token}"}
        )
        assert pan_resp.status_code == 200
        assert pan_resp.json()["status"] == "success"

        # 8. Negative Test: Firm/Company PAN Rejected (4th char 'C' not 'P')
        pan_bad_resp = client.post(
            "/api/v1/worker/kyc/verify-pan",
            json={"pan_number": "ABCCE1234F", "document_url": "https://storage.hstaff.com/kyc/pan.jpg"},
            headers={"Authorization": f"Bearer {fresh_worker_token}"}
        )
        assert pan_bad_resp.status_code == 400

        # 9. Admin Approves KYC & Dispatches Email
        review = client.post(
            "/api/v1/admin/kyc/wrk_profile_001/review",
            json={"action": "approved", "remarks": "Format verified, manual check passed"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert review.status_code == 200
        assert review.json()["notification_dispatched"] is True

        # 10. CRITICAL NEGATIVE TEST: Assignment Ownership Enforcement
        # Worker 1 (Amit) tries to clock in to Worker 2's assignment (asg_001) -> Must be Forbidden (403)
        qr_token_shift2 = GeofenceVerificationService.generate_signed_qr_token("shf_002", "usr_biz_001")
        ownership_attack = client.post(
            "/api/v1/tracking/attendance/clock-in",
            json={
                "assignment_id": "asg_001",
                "signed_qr_token": qr_token_shift2,
                "latitude": 19.0596,
                "longitude": 72.8295
            },
            headers={"Authorization": f"Bearer {fresh_worker_token}"}
        )
        assert ownership_attack.status_code == 403
        assert "Ownership violation" in ownership_attack.json()["detail"]

        # 11. POSITIVE CLOCK-IN TEST: Genuine assignment (asg_amit_001 on shf_001)
        qr_token_shift1 = GeofenceVerificationService.generate_signed_qr_token("shf_001", "usr_biz_001")
        valid_clock_in = client.post(
            "/api/v1/tracking/attendance/clock-in",
            json={
                "assignment_id": "asg_amit_001",
                "signed_qr_token": qr_token_shift1,
                "latitude": 19.1197,
                "longitude": 72.8464
            },
            headers={"Authorization": f"Bearer {fresh_worker_token}"}
        )
        assert valid_clock_in.status_code == 200
        assert valid_clock_in.json()["status"] == "success"

        # 12. NEGATIVE TEST: Prevent Duplicate Clock-in
        duplicate_clock_in = client.post(
            "/api/v1/tracking/attendance/clock-in",
            json={
                "assignment_id": "asg_amit_001",
                "signed_qr_token": qr_token_shift1,
                "latitude": 19.1197,
                "longitude": 72.8464
            },
            headers={"Authorization": f"Bearer {fresh_worker_token}"}
        )
        assert duplicate_clock_in.status_code == 400

        # 13. Mathematical Split Formula Verification (15% Commission, 18% GST on Comm, 1% TDS)
        split = payment_engine.calculate_hstaff_split(1000.0, commission_percentage=15.0, amortize_kit=False)
        assert split["gross_amount"] == 1000.0
        assert split["platform_commission"] == 150.0
        assert split["gst_on_commission"] == 27.0
        assert split["tds_deduction"] == 10.0
        assert split["net_worker_payout"] == 840.0

        # 14. Payout Settlement API (Sandbox Mode Tagged)
        payout_resp = client.post(
            "/api/v1/payments/pay_001/release-payout",
            json={"payout_account": "rohit@okaxis", "notes": "Shift Completion Wage"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert payout_resp.status_code == 200
        assert "bank_rrn" in payout_resp.json()["gateway_response"]

        # 15. Anti-GPS Spoofing / Impossible Travel Speed Test
        t1 = datetime.now(timezone.utc)
        t2 = t1 + timedelta(minutes=5)
        is_fraud, speed = GeofenceVerificationService.check_impossible_travel(
            19.1197, 72.8464, t1,
            28.6139, 77.2090, t2
        )
        assert is_fraud is True
        assert speed > 1000.0

        # 16. Immutable Audit Trail Inspection
        audit = client.get("/api/v1/audit/logs", headers={"Authorization": f"Bearer {admin_token}"})
        assert audit.status_code == 200
        assert len(audit.json()) > 0