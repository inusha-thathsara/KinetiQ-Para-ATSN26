"""Two-layer privacy schemas.

CRITICAL PRIVACY BOUNDARY:
- `PrivateHealthView` and `PrivateClipView` are strictly for Athlete + Coach routers.
- `ScoutPassportView` is the ONLY athlete view model the Scout router is allowed to import.
  It structurally omits ACWR, session load spikes, shoulder/limb injury flags, baseline
  fault deltas, coaching cues, and private coach health notes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserSummary(BaseModel):
    id: int
    email: str
    full_name: str
    full_name_ar: str
    role: Literal["athlete", "coach", "scout"]
    country: str
    affiliation: str
    affiliation_ar: str
    athlete_id: int | None = None
    ipc_class: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class AchievementOut(BaseModel):
    id: int
    event_name: str
    ipc_class: str
    result_value: str
    result_seconds: float
    competition_name: str
    achieved_date: date
    proof_reference: str
    verification_tier: Literal["self_reported", "coach_verified", "organizer_verified"]
    is_pb: bool


class AchievementCreate(BaseModel):
    athlete_id: int | None = None
    event_name: str = Field(..., examples=["400m"])
    ipc_class: str = Field(..., examples=["T54"])
    result_value: str = Field(..., examples=["50.84s"])
    result_seconds: float = Field(..., gt=0)
    competition_name: str
    achieved_date: date
    proof_reference: str = ""
    is_pb: bool = True


class AchievementVerifyRequest(BaseModel):
    verification_tier: Literal["coach_verified", "organizer_verified"] = "coach_verified"


class SessionCreate(BaseModel):
    title: str
    event_group: str
    limb_load_type: Literal["upper_limb", "lower_limb"]
    session_date: date
    duration_min: float = Field(45.0, gt=0)
    distance_m: float = Field(0.0, ge=0)
    intensity_rpe: float = Field(7.0, ge=1, le=10)
    attendee_ids: list[int] = Field(default_factory=list)
    notes: str = ""


class CoachNoteCreate(BaseModel):
    athlete_id: int
    note_text: str
    load_adjustment: Literal["monitor", "taper_20pct", "rest_48h", "physio_refer"] = "taper_20pct"


class PrivacyToggleRequest(BaseModel):
    passport_public: bool


class DemoClipAnalyzeRequest(BaseModel):
    athlete_id: int | None = None
    module_type: Literal["wheelchair_propulsion", "standing_para_gait", "guide_runner_sync"] = "wheelchair_propulsion"
    scenario: Literal["fatigue_spike", "optimal_baseline"] = "fatigue_spike"
    witness_badge: Literal["coach_witnessed", "self_submitted"] = "coach_witnessed"


# ---------------------------------------------------------------------------
# LAYER 1: PRIVATE HEALTH & RISK VIEW (ATHLETE + COACH ONLY)
# ---------------------------------------------------------------------------
class PrivateClipView(BaseModel):
    id: int
    athlete_id: int
    module_type: str
    status: str
    error_message: str = ""
    witness_badge: str
    recorded_at: datetime
    overlay_url: str | None = None
    keyframe_urls: list[str] = Field(default_factory=list)
    detection_confidence: float
    form_score: float
    metrics_json: dict
    baseline_deltas_json: dict
    risk_level: str
    findings_json: list
    cue_en: str
    cue_ar: str
    confidence_note_en: str
    confidence_note_ar: str
    ai_source: str
    is_curated_for_passport: bool
    is_demo_sample: bool


class PrivateHealthView(BaseModel):
    athlete_id: int
    full_name: str
    full_name_ar: str
    ipc_class: str
    disability_category: str
    limb_load_type: str
    primary_events: list[str]
    passport_public: bool
    is_demo_data: bool
    load_summary: dict
    latest_clip: PrivateClipView | None = None
    recent_clips: list[PrivateClipView] = Field(default_factory=list)
    achievements: list[AchievementOut] = Field(default_factory=list)
    coach_notes: list[dict] = Field(default_factory=list)
    disclaimer_en: str = (
        "Decision-support risk indicator only — not medical diagnosis or official IPC classification. "
        "Consult a qualified sports physiotherapist for Red-zone alerts."
    )
    disclaimer_ar: str = (
        "مؤشر دعم قرار فقط وليس تشخيصاً طبياً أو تصنيفاً رسمياً للجنة البارالمبية. "
        "يُرجى استشارة أخصائي علاج طبيعي رياضي عند ظهور تنبيهات المنطقة الحمراء."
    )


# ---------------------------------------------------------------------------
# LAYER 2: SCOUT-FACING PASSPORT VIEW (STRICTLY ZERO HEALTH/RISK DATA)
# ---------------------------------------------------------------------------
class ScoutCuratedClip(BaseModel):
    id: int
    module_type: str
    recorded_at: datetime
    overlay_url: str | None = None
    witness_badge: str
    form_score: float


class ScoutFormTrendPoint(BaseModel):
    recorded_date: str
    form_score: float


class ScoutPassportView(BaseModel):
    athlete_id: int
    full_name: str
    full_name_ar: str
    country: str
    affiliation: str
    affiliation_ar: str
    ipc_class: str
    disability_category: str
    primary_events: list[str]
    bio_en: str
    bio_ar: str
    is_demo_data: bool
    form_consistency_score: float
    form_trend: list[ScoutFormTrendPoint] = Field(default_factory=list)
    coach_confirmed_sessions_30d: int
    achievements: list[AchievementOut] = Field(default_factory=list)
    curated_clips: list[ScoutCuratedClip] = Field(default_factory=list)
    ai_scout_summary_en: str
    ai_scout_summary_ar: str
    shortlisted: bool = False
    contact_requested: bool = False


class NLScoutSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)


class NLScoutSearchResponse(BaseModel):
    query: str
    interpreted_filters: dict
    translation_source: str
    results: list[ScoutPassportView]


class ShortlistRequest(BaseModel):
    note: str = ""
    contact_requested: bool = False
