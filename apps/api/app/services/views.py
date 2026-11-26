"""Strict 2-layer serializer builders (PrivateHealthView vs ScoutPassportView)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.gemini_client import generate_scout_summary
from app.load.acwr import evaluate_athlete_load
from app.models import (
    Achievement,
    AthleteProfile,
    CoachActionNote,
    FormClip,
    ScoutShortlist,
    SessionAttendance,
    TrainingSession,
)
from app.schemas.privacy import (
    AchievementOut,
    PrivateClipView,
    PrivateHealthView,
    ScoutCuratedClip,
    ScoutFormTrendPoint,
    ScoutPassportView,
)


def serialize_achievement(a: Achievement) -> AchievementOut:
    return AchievementOut(
        id=a.id,
        event_name=a.event_name,
        ipc_class=a.ipc_class,
        result_value=a.result_value,
        result_seconds=a.result_seconds,
        competition_name=a.competition_name,
        achieved_date=a.achieved_date,
        proof_reference=a.proof_reference,
        verification_tier=a.verification_tier,
        is_pb=a.is_pb,
    )


def serialize_private_clip(clip: FormClip) -> PrivateClipView:
    return PrivateClipView(
        id=clip.id,
        athlete_id=clip.athlete_id,
        module_type=clip.module_type,
        status=clip.status,
        error_message=clip.error_message,
        witness_badge=clip.witness_badge,
        recorded_at=clip.recorded_at,
        overlay_url=f"/api/media/{clip.overlay_filename}" if clip.overlay_filename else None,
        keyframe_urls=[f"/api/media/{kf}" for kf in (clip.keyframe_filenames or [])],
        detection_confidence=clip.detection_confidence,
        form_score=clip.form_score,
        metrics_json=clip.metrics_json or {},
        baseline_deltas_json=clip.baseline_deltas_json or {},
        risk_level=clip.risk_level,
        findings_json=clip.findings_json or [],
        cue_en=clip.cue_en,
        cue_ar=clip.cue_ar,
        confidence_note_en=clip.confidence_note_en,
        confidence_note_ar=clip.confidence_note_ar,
        ai_source=clip.ai_source,
        is_curated_for_passport=clip.is_curated_for_passport,
        is_demo_sample=clip.is_demo_sample,
    )


def get_athlete_attendances(db: Session, athlete_id: int) -> list[tuple[SessionAttendance, TrainingSession]]:
    return (
        db.query(SessionAttendance, TrainingSession)
        .join(TrainingSession, SessionAttendance.session_id == TrainingSession.id)
        .filter(SessionAttendance.athlete_id == athlete_id)
        .all()
    )


def build_private_health_view(db: Session, athlete: AthleteProfile) -> PrivateHealthView:
    clips = (
        db.query(FormClip)
        .filter_by(athlete_id=athlete.id)
        .order_by(FormClip.recorded_at.desc(), FormClip.id.desc())
        .limit(8)
        .all()
    )
    latest_completed = next((c for c in clips if c.status == "completed"), clips[0] if clips else None)
    att_rows = get_athlete_attendances(db, athlete.id)
    load_summary = evaluate_athlete_load(att_rows, athlete.limb_load_type, latest_completed)

    achievements = (
        db.query(Achievement)
        .filter_by(athlete_id=athlete.id)
        .order_by(Achievement.achieved_date.desc())
        .all()
    )
    notes = (
        db.query(CoachActionNote)
        .filter_by(athlete_id=athlete.id)
        .order_by(CoachActionNote.created_at.desc())
        .limit(5)
        .all()
    )

    return PrivateHealthView(
        athlete_id=athlete.id,
        full_name=athlete.user.full_name,
        full_name_ar=athlete.user.full_name_ar or athlete.user.full_name,
        ipc_class=athlete.ipc_class,
        disability_category=athlete.disability_category,
        limb_load_type=athlete.limb_load_type,
        primary_events=athlete.primary_events or [],
        passport_public=athlete.passport_public,
        is_demo_data=athlete.is_demo_data,
        load_summary=load_summary,
        latest_clip=serialize_private_clip(latest_completed) if latest_completed else None,
        recent_clips=[serialize_private_clip(c) for c in clips],
        achievements=[serialize_achievement(a) for a in achievements],
        coach_notes=[
            {
                "id": n.id,
                "note_text": n.note_text,
                "load_adjustment": n.load_adjustment,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ],
    )


def build_scout_passport_view(
    db: Session,
    athlete: AthleteProfile,
    scout_user_id: int | None = None,
) -> ScoutPassportView:
    """Strictly builds the Scout-Facing Passport with ZERO private health/risk/load fields."""
    completed_clips = (
        db.query(FormClip)
        .filter_by(athlete_id=athlete.id, status="completed")
        .order_by(FormClip.recorded_at.asc())
        .all()
    )
    scores = [c.form_score for c in completed_clips if c.form_score > 0]
    consistency = round(sum(scores) / len(scores), 1) if scores else 85.0
    trend = [
        ScoutFormTrendPoint(
            recorded_date=c.recorded_at.date().isoformat(),
            form_score=round(c.form_score, 1),
        )
        for c in completed_clips[-6:]
    ]
    curated = [
        ScoutCuratedClip(
            id=c.id,
            module_type=c.module_type,
            recorded_at=c.recorded_at,
            overlay_url=f"/api/media/{c.overlay_filename}" if c.overlay_filename else None,
            witness_badge=c.witness_badge,
            form_score=round(c.form_score, 1),
        )
        for c in reversed(completed_clips)
        if c.is_curated_for_passport
    ][:4]

    att_rows = get_athlete_attendances(db, athlete.id)
    # Count only coach-confirmed sessions in last 30 days — NEVER expose load numbers or ACWR!
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=30)
    confirmed_sessions_30d = sum(
        1 for att, sess in att_rows if att.attended and att.coach_confirmed and sess.session_date >= cutoff
    )

    achievements = (
        db.query(Achievement)
        .filter_by(athlete_id=athlete.id)
        .order_by(Achievement.achieved_date.desc())
        .all()
    )

    shortlisted = False
    contact_requested = False
    if scout_user_id is not None:
        sl = (
            db.query(ScoutShortlist)
            .filter_by(scout_id=scout_user_id, athlete_id=athlete.id)
            .first()
        )
        if sl:
            shortlisted = True
            contact_requested = sl.contact_requested

    return ScoutPassportView(
        athlete_id=athlete.id,
        full_name=athlete.user.full_name,
        full_name_ar=athlete.user.full_name_ar or athlete.user.full_name,
        country=athlete.user.country,
        affiliation=athlete.user.affiliation,
        affiliation_ar=athlete.user.affiliation_ar or athlete.user.affiliation,
        ipc_class=athlete.ipc_class,
        disability_category=athlete.disability_category,
        primary_events=athlete.primary_events or [],
        bio_en=athlete.bio_en,
        bio_ar=athlete.bio_ar,
        is_demo_data=athlete.is_demo_data,
        form_consistency_score=consistency,
        form_trend=trend,
        coach_confirmed_sessions_30d=confirmed_sessions_30d,
        achievements=[serialize_achievement(a) for a in achievements],
        curated_clips=curated,
        ai_scout_summary_en=athlete.ai_scout_summary_en,
        ai_scout_summary_ar=athlete.ai_scout_summary_ar,
        shortlisted=shortlisted,
        contact_requested=contact_requested,
    )


def refresh_scout_summary_from_safe_view(db: Session, athlete: AthleteProfile) -> None:
    """Regenerates EN/AR AI scout summary strictly from ScoutPassportView data."""
    safe_view = build_scout_passport_view(db, athlete)
    safe_dict = safe_view.model_dump(mode="json")
    sum_en, sum_ar, _src = generate_scout_summary(safe_dict)
    athlete.ai_scout_summary_en = sum_en
    athlete.ai_scout_summary_ar = sum_ar
    db.commit()
