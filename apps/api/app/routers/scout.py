"""Scout router — STRICTLY imports ScoutPassportView only (2-layer privacy boundary)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.ai.gemini_client import translate_scout_nl_query
from app.database import get_db
from app.models import AthleteProfile, ScoutShortlist, User
from app.schemas.privacy import (
    NLScoutSearchRequest,
    NLScoutSearchResponse,
    ScoutPassportView,
    ShortlistRequest,
)
from app.security import get_current_user, require_roles
from app.services.pdf_export import render_passport_pdf
from app.services.views import build_scout_passport_view

router = APIRouter(prefix="/api/scout", tags=["scout"])


def _filter_passports(
    passports: list[ScoutPassportView],
    ipc_class: str | None = None,
    disability_category: str | None = None,
    event: str | None = None,
    max_seconds: float | None = None,
    verified_only: bool = False,
    country: str | None = None,
    q: str | None = None,
) -> list[ScoutPassportView]:
    out = []
    for p in passports:
        if ipc_class and p.ipc_class.upper() != ipc_class.upper():
            continue
        if disability_category and p.disability_category != disability_category:
            continue
        if country and country.lower() not in p.country.lower():
            continue
        if event:
            ev_l = event.lower()
            has_ev = any(ev_l == e.lower() for e in p.primary_events) or any(
                ev_l == a.event_name.lower() for a in p.achievements
            )
            if not has_ev:
                continue
        if verified_only:
            if not any(a.verification_tier != "self_reported" for a in p.achievements):
                continue
        if max_seconds is not None:
            matching = [
                a
                for a in p.achievements
                if (not event or a.event_name.lower() == event.lower())
                and (not verified_only or a.verification_tier != "self_reported")
                and a.result_seconds <= max_seconds
            ]
            if not matching:
                continue
        if q:
            hay = f"{p.full_name} {p.full_name_ar} {p.ipc_class} {p.country} {p.affiliation} {' '.join(p.primary_events)}".lower()
            if q.lower() not in hay:
                continue
        out.append(p)
    return out


@router.get("/passports", response_model=list[ScoutPassportView])
def list_passports(
    ipc_class: str | None = None,
    disability_category: str | None = None,
    event: str | None = None,
    max_seconds: float | None = None,
    verified_only: bool = False,
    country: str | None = None,
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athletes = db.query(AthleteProfile).filter_by(passport_public=True).order_by(AthleteProfile.id.asc()).all()
    scout_id = user.id if user.role == "scout" else None
    views = [build_scout_passport_view(db, a, scout_user_id=scout_id) for a in athletes]
    return _filter_passports(
        views,
        ipc_class=ipc_class,
        disability_category=disability_category,
        event=event,
        max_seconds=max_seconds,
        verified_only=verified_only,
        country=country,
        q=q,
    )


@router.post("/nl-search", response_model=NLScoutSearchResponse)
def nl_search_passports(
    body: NLScoutSearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters, src = translate_scout_nl_query(body.query)
    athletes = db.query(AthleteProfile).filter_by(passport_public=True).order_by(AthleteProfile.id.asc()).all()
    scout_id = user.id if user.role == "scout" else None
    views = [build_scout_passport_view(db, a, scout_user_id=scout_id) for a in athletes]
    results = _filter_passports(
        views,
        ipc_class=filters.get("ipc_class"),
        disability_category=filters.get("disability_category"),
        event=filters.get("event"),
        max_seconds=filters.get("max_seconds"),
        verified_only=bool(filters.get("verified_only", False)),
        country=filters.get("country"),
    )
    return NLScoutSearchResponse(
        query=body.query,
        interpreted_filters=filters,
        translation_source=src,
        results=results,
    )


@router.get("/passports/{athlete_id}", response_model=ScoutPassportView)
def get_passport(
    athlete_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = db.get(AthleteProfile, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Passport not found")
    if not athlete.passport_public and user.role == "scout":
        raise HTTPException(status_code=403, detail="This Para-Athlete Passport is set to private")
    scout_id = user.id if user.role == "scout" else None
    return build_scout_passport_view(db, athlete, scout_user_id=scout_id)


@router.get("/passports/{athlete_id}/pdf")
def export_passport_pdf(
    athlete_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    athlete = db.get(AthleteProfile, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Passport not found")
    if not athlete.passport_public and user.role == "scout":
        raise HTTPException(status_code=403, detail="This Para-Athlete Passport is set to private")
    passport = build_scout_passport_view(db, athlete, scout_user_id=user.id if user.role == "scout" else None)
    pdf_bytes = render_passport_pdf(passport)
    safe_slug = athlete.user.full_name.lower().replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="kinetiq_para_passport_{safe_slug}.pdf"'},
    )


@router.post("/shortlist/{athlete_id}")
def shortlist_athlete(
    athlete_id: int,
    body: ShortlistRequest,
    user: User = Depends(require_roles("scout")),
    db: Session = Depends(get_db),
):
    athlete = db.get(AthleteProfile, athlete_id)
    if not athlete or not athlete.passport_public:
        raise HTTPException(status_code=404, detail="Public passport not found")
    sl = db.query(ScoutShortlist).filter_by(scout_id=user.id, athlete_id=athlete.id).first()
    if sl:
        sl.note = body.note or sl.note
        sl.contact_requested = body.contact_requested or sl.contact_requested
    else:
        sl = ScoutShortlist(
            scout_id=user.id,
            athlete_id=athlete.id,
            note=body.note,
            contact_requested=body.contact_requested,
        )
        db.add(sl)
    db.commit()
    return {
        "athlete_id": athlete.id,
        "shortlisted": True,
        "contact_requested": sl.contact_requested,
        "note": sl.note,
    }
