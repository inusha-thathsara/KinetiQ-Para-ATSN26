from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.privacy import LoginRequest, LoginResponse, UserSummary
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_summary(user: User) -> UserSummary:
    ap = user.athlete_profile
    return UserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        full_name_ar=user.full_name_ar or user.full_name,
        role=user.role,
        country=user.country,
        affiliation=user.affiliation,
        affiliation_ar=user.affiliation_ar or user.affiliation,
        athlete_id=ap.id if ap else None,
        ipc_class=ap.ipc_class if ap else None,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=_to_summary(user))


@router.get("/me", response_model=UserSummary)
def me(user: User = Depends(get_current_user)):
    return _to_summary(user)


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Public list of seeded demo accounts for instant ATSN'26 evaluation switching."""
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "email": u.email,
            "password": "demo1234",
            "full_name": u.full_name,
            "full_name_ar": u.full_name_ar,
            "role": u.role,
            "ipc_class": u.athlete_profile.ipc_class if u.athlete_profile else None,
            "disability_category": u.athlete_profile.disability_category if u.athlete_profile else None,
        }
        for u in users
    ]
