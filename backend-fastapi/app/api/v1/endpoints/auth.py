import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, get_current_user
from app.models.models import User, WorkerProfile, UserRole, KYCStatus
from app.schemas.schemas import UserRegisterRequest, TokenResponse, UserResponse
from app.services.audit_service import AuditLogger

router = APIRouter(prefix="/auth", tags=["IAM & Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        user_id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True
    )
    db.add(user)
    db.flush()

    if payload.role == UserRole.WORKER:
        worker = WorkerProfile(
            worker_id=str(uuid.uuid4()),
            user_id=user.user_id,
            phone=payload.phone,
            kyc_status=KYCStatus.PENDING
        )
        db.add(worker)

    db.commit()
    db.refresh(user)

    AuditLogger.write(db, user.user_id, user.role.value, "USER_REGISTERED", f"user:{user.user_id}", request=request)
    return user

@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Deactivated account")

    access_token = create_access_token({"sub": user.user_id, "role": user.role.value})
    refresh_token = create_refresh_token({"sub": user.user_id, "role": user.role.value})

    AuditLogger.write(db, user.user_id, user.role.value, "USER_LOGIN", f"user:{user.user_id}", request=request)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user_id=user.user_id,
        role=user.role,
        name=user.name
    )

@router.get("/me", response_model=UserResponse)
def get_user_profile(user: User = Depends(get_current_user)):
    return user
