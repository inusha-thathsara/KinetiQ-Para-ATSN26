from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Achievement, AthleteProfile, User
from app.schemas.privacy import (
    AchievementCreate,
    AchievementOut,
    AchievementVerifyRequest,
    PrivacyToggleRequest,
    PrivateHealthView,
)
from app.security import require_roles
from app.services.views import (
    build_private_health_view,
    refresh_scout_summary_from_safe_view,
    serialize_achievement,
)

router = APIRouter(tags=["dashboard-and-verification"])


@router.get("/api/athlete/me/dashboard", response_model=PrivateHealthView)
def athlete_dashboard(
    user: User = Depends(require_roles("athlete")),
    db: Session = Depends(get_db),
):
    if not user.athlete_profile:
        raise HTTPException(status_code=404, detail="Athlete profile not found")
    return build_private_health_view(db, user.athlete_profile)


@router.get("/api/coach/readiness", response_model=list[PrivateHealthView])
def coach_readiness_dashboard(
    user: User = Depends(require_roles("coach")),
    db: Session = Depends(get_db),
):
    athletes = db.query(AthleteProfile).order_by(AthleteProfile.id.asc()).all()
    views = [build_private_health_view(db, a) for a in athletes]
    # Sort most urgent (lowest readiness score) first
    views.sort(key=lambda v: v.load_summary.get("readiness_score", 100))
    return views


@router.post("/api/achievements", response_model=AchievementOut)
def log_achievement(
    body: AchievementCreate,
    user: User = Depends(require_roles("athlete", "coach")),
    db: Session = Depends(get_db),
):
    if user.role == "athlete":
        if not user.athlete_profile:
            raise HTTPException(status_code=404, detail="Athlete profile not found")
        athlete = user.athlete_profile
        tier = "self_reported"
    else:
        athlete = db.get(AthleteProfile, body.athlete_id) if body.athlete_id else db.query(AthleteProfile).first()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        tier = "coach_verified"

    ach = Achievement(
        athlete_id=athlete.id,
        event_name=body.event_name,
        ipc_class=body.ipc_class,
        result_value=body.result_value,
        result_seconds=body.result_seconds,
        competition_name=body.competition_name,
        achieved_date=body.achieved_date,
        proof_reference=body.proof_reference,
        verification_tier=tier,
        verified_by_id=user.id if tier != "self_reported" else None,
        verified_at=datetime.now(UTC) if tier != "self_reported" else None,
        is_pb=body.is_pb,
    )
    db.add(ach)
    db.commit()
    db.refresh(ach)
    refresh_scout_summary_from_safe_view(db, athlete)
    return serialize_achievement(ach)


@router.patch("/api/achievements/{achievement_id}/verify", response_model=AchievementOut)
def verify_achievement(
    achievement_id: int,
    body: AchievementVerifyRequest,
    user: User = Depends(require_roles("coach")),
    db: Session = Depends(get_db),
):
    ach = db.get(Achievement, achievement_id)
    if not ach:
        raise HTTPException(status_code=404, detail="Achievement not found")
    ach.verification_tier = body.verification_tier
    ach.verified_by_id = user.id
    ach.verified_at = datetime.now(UTC)
    db.commit()
    db.refresh(ach)

    athlete = db.get(AthleteProfile, ach.athlete_id)
    if athlete:
        refresh_scout_summary_from_safe_view(db, athlete)
    return serialize_achievement(ach)


@router.patch("/api/athletes/{athlete_id}/privacy")
def toggle_passport_privacy(
    athlete_id: int,
    body: PrivacyToggleRequest,
    user: User = Depends(require_roles("athlete", "coach")),
    db: Session = Depends(get_db),
):
    athlete = db.get(AthleteProfile, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    if user.role == "athlete" and (not user.athlete_profile or user.athlete_profile.id != athlete.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    athlete.passport_public = body.passport_public
    db.commit()
    return {"athlete_id": athlete.id, "passport_public": athlete.passport_public}
