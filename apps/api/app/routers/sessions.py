from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.load.acwr import compute_session_load, evaluate_athlete_load
from app.models import AthleteProfile, CoachActionNote, FormClip, SessionAttendance, TrainingSession, User
from app.schemas.privacy import CoachNoteCreate, SessionCreate
from app.security import require_roles
from app.services.views import get_athlete_attendances

router = APIRouter(tags=["sessions"])


@router.post("/api/sessions")
def create_session(
    body: SessionCreate,
    user: User = Depends(require_roles("coach")),
    db: Session = Depends(get_db),
):
    load = compute_session_load(
        body.limb_load_type, body.duration_min, body.distance_m, body.intensity_rpe
    )
    sess = TrainingSession(
        coach_id=user.id,
        title=body.title,
        event_group=body.event_group,
        limb_load_type=body.limb_load_type,
        session_date=body.session_date,
        duration_min=body.duration_min,
        distance_m=body.distance_m,
        intensity_rpe=body.intensity_rpe,
        computed_load=load,
        notes=body.notes,
    )
    db.add(sess)
    db.flush()

    updated_athletes = []
    for aid in body.attendee_ids:
        athlete = db.get(AthleteProfile, aid)
        if not athlete:
            continue
        db.add(SessionAttendance(session_id=sess.id, athlete_id=aid, attended=True, coach_confirmed=True))
        updated_athletes.append(aid)

    db.commit()
    db.refresh(sess)

    # Return updated load summaries for attendees so Coach Dashboard refreshes immediately
    impacts = []
    for aid in updated_athletes:
        athlete = db.get(AthleteProfile, aid)
        latest_clip = (
            db.query(FormClip)
            .filter_by(athlete_id=aid, status="completed")
            .order_by(FormClip.recorded_at.desc())
            .first()
        )
        summary = evaluate_athlete_load(get_athlete_attendances(db, aid), athlete.limb_load_type, latest_clip)
        impacts.append({"athlete_id": aid, "full_name": athlete.user.full_name, "load_summary": summary})

    return {
        "id": sess.id,
        "title": sess.title,
        "computed_load": sess.computed_load,
        "attendee_count": len(updated_athletes),
        "athlete_impacts": impacts,
    }


@router.get("/api/sessions")
def list_sessions(
    user: User = Depends(require_roles("coach")),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(TrainingSession)
        .order_by(TrainingSession.session_date.desc(), TrainingSession.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "event_group": s.event_group,
            "limb_load_type": s.limb_load_type,
            "session_date": s.session_date.isoformat(),
            "duration_min": s.duration_min,
            "distance_m": s.distance_m,
            "intensity_rpe": s.intensity_rpe,
            "computed_load": s.computed_load,
            "attendee_ids": [a.athlete_id for a in s.attendances if a.attended],
        }
        for s in sessions
    ]


@router.post("/api/coach/notes")
def add_coach_note(
    body: CoachNoteCreate,
    user: User = Depends(require_roles("coach")),
    db: Session = Depends(get_db),
):
    athlete = db.get(AthleteProfile, body.athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    note = CoachActionNote(
        coach_id=user.id,
        athlete_id=athlete.id,
        note_text=body.note_text,
        load_adjustment=body.load_adjustment,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "athlete_id": note.athlete_id,
        "note_text": note.note_text,
        "load_adjustment": note.load_adjustment,
        "created_at": note.created_at.isoformat(),
    }
