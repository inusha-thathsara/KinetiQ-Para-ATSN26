from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name_ar: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # athlete | coach | scout
    country: Mapped[str] = mapped_column(String(100), default="Sri Lanka")
    affiliation: Mapped[str] = mapped_column(String(200), default="")
    affiliation_ar: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    athlete_profile: Mapped["AthleteProfile | None"] = relationship(
        back_populates="user", foreign_keys="AthleteProfile.user_id", uselist=False
    )


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    ipc_class: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # T54, T64, T37, T12, T40
    disability_category: Mapped[str] = mapped_column(String(64), nullable=False)
    # wheelchair_racing | prosthetic_standing | cerebral_palsy_standing | visual_impairment | short_stature
    limb_load_type: Mapped[str] = mapped_column(String(32), default="lower_limb")  # upper_limb | lower_limb
    primary_events: Mapped[list] = mapped_column(JSON, default=list)
    passport_public: Mapped[bool] = mapped_column(Boolean, default=True)
    bio_en: Mapped[str] = mapped_column(Text, default="")
    bio_ar: Mapped[str] = mapped_column(Text, default="")
    ai_scout_summary_en: Mapped[str] = mapped_column(Text, default="")
    ai_scout_summary_ar: Mapped[str] = mapped_column(Text, default="")
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="athlete_profile", foreign_keys=[user_id])
    coach: Mapped[User | None] = relationship(foreign_keys=[coach_id])
    clips: Mapped[list["FormClip"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    achievements: Mapped[list["Achievement"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")
    baselines: Mapped[list["AthleteBaseline"]] = relationship(back_populates="athlete", cascade="all, delete-orphan")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_group: Mapped[str] = mapped_column(String(100), nullable=False)
    limb_load_type: Mapped[str] = mapped_column(String(32), nullable=False)  # upper_limb | lower_limb
    session_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    duration_min: Mapped[float] = mapped_column(Float, default=45.0)
    distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    intensity_rpe: Mapped[float] = mapped_column(Float, default=7.0)  # 1-10 scale
    computed_load: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attendances: Mapped[list["SessionAttendance"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SessionAttendance(Base):
    __tablename__ = "session_attendances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.id", ondelete="CASCADE"), nullable=False)
    attended: Mapped[bool] = mapped_column(Boolean, default=True)
    coach_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)

    session: Mapped[TrainingSession] = relationship(back_populates="attendances")


class FormClip(Base):
    __tablename__ = "form_clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.id", ondelete="CASCADE"), nullable=False)
    module_type: Mapped[str] = mapped_column(String(48), nullable=False)
    # wheelchair_propulsion | standing_para_gait | guide_runner_sync
    video_filename: Mapped[str] = mapped_column(String(255), default="")
    overlay_filename: Mapped[str] = mapped_column(String(255), default="")
    keyframe_filenames: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)  # queued|processing|completed|failed
    error_message: Mapped[str] = mapped_column(Text, default="")
    witness_badge: Mapped[str] = mapped_column(String(32), default="self_submitted")  # coach_witnessed|self_submitted

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    detection_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    form_score: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_deltas_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(32), default="baseline_building")  # green|amber|red|baseline_building
    findings_json: Mapped[list] = mapped_column(JSON, default=list)
    cue_en: Mapped[str] = mapped_column(Text, default="")
    cue_ar: Mapped[str] = mapped_column(Text, default="")
    confidence_note_en: Mapped[str] = mapped_column(Text, default="")
    confidence_note_ar: Mapped[str] = mapped_column(Text, default="")
    ai_source: Mapped[str] = mapped_column(String(32), default="template_fallback")  # gemini|template_fallback|cached
    is_curated_for_passport: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo_sample: Mapped[bool] = mapped_column(Boolean, default=False)

    athlete: Mapped[AthleteProfile] = relationship(back_populates="clips")


class AthleteBaseline(Base):
    __tablename__ = "athlete_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.id", ondelete="CASCADE"), nullable=False)
    module_type: Mapped[str] = mapped_column(String(48), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    values_history: Mapped[list] = mapped_column(JSON, default=list)
    median_val: Mapped[float] = mapped_column(Float, default=0.0)
    mad_val: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    athlete: Mapped[AthleteProfile] = relationship(back_populates="baselines")


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.id", ondelete="CASCADE"), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)  # 100m, 400m, 800m
    ipc_class: Mapped[str] = mapped_column(String(16), nullable=False)
    result_value: Mapped[str] = mapped_column(String(32), nullable=False)  # "50.84s"
    result_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    competition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    achieved_date: Mapped[date] = mapped_column(Date, nullable=False)
    proof_reference: Mapped[str] = mapped_column(String(255), default="")
    verification_tier: Mapped[str] = mapped_column(String(32), default="self_reported")
    # self_reported | coach_verified | organizer_verified
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_pb: Mapped[bool] = mapped_column(Boolean, default=True)

    athlete: Mapped[AthleteProfile] = relationship(back_populates="achievements")


class ScoutShortlist(Base):
    __tablename__ = "scout_shortlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scout_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    contact_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CoachActionNote(Base):
    __tablename__ = "coach_action_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.id", ondelete="CASCADE"), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    load_adjustment: Mapped[str] = mapped_column(String(64), default="monitor")  # monitor|taper_20pct|rest_48h|physio_refer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
