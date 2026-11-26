from __future__ import annotations

import uuid
from pathlib import Path

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.ai.gemini_client import generate_coaching_feedback
from app.config import settings
from app.cv.baseline import evaluate_and_update_baseline
from app.cv.metrics import compute_module_metrics
from app.cv.pose import generate_synthetic_demo_clip, process_video_pose
from app.database import SessionLocal, get_db
from app.load.acwr import evaluate_athlete_load
from app.models import AthleteProfile, FormClip, User
from app.schemas.privacy import DemoClipAnalyzeRequest, PrivateClipView
from app.security import get_current_user, require_roles
from app.services.views import (
    get_athlete_attendances,
    refresh_scout_summary_from_safe_view,
    serialize_private_clip,
)

router = APIRouter(tags=["clips"])


def _run_clip_analysis(clip_id: int, video_path: Path, precomputed_frames: list[dict] | None = None, fps: float = 15.0) -> None:
    db = SessionLocal()
    try:
        clip = db.get(FormClip, clip_id)
        if not clip:
            return
        clip.status = "processing"
        db.commit()

        athlete = db.get(AthleteProfile, clip.athlete_id)
        if not athlete:
            clip.status = "failed"
            clip.error_message = "Athlete not found"
            db.commit()
            return

        prefix = f"clip_{clip.id}_{uuid.uuid4().hex[:6]}"
        if precomputed_frames is None:
            pose_res = process_video_pose(video_path, clip.module_type, prefix)
            frames = pose_res["frames"]
            fps = pose_res["fps"]
            clip.overlay_filename = pose_res["overlay_filename"]
            clip.keyframe_filenames = pose_res["keyframe_filenames"]
        else:
            # Demo clip already rendered to H.264 overlay; extract 3 keyframes from it
            clip.overlay_filename = video_path.name
            cap = cv2.VideoCapture(str(video_path))
            kfs: list[str] = []
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 60)
            for ki, target_idx in enumerate([max(1, total // 5), total // 2, max(2, int(total * 0.8))]):
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                ok, fr = cap.read()
                if ok:
                    kf_name = f"{prefix}_kf_{ki + 1}.jpg"
                    cv2.imwrite(str(settings.storage_dir / kf_name), fr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    kfs.append(kf_name)
            cap.release()
            clip.keyframe_filenames = kfs
            frames = precomputed_frames

        metrics_res = compute_module_metrics(clip.module_type, frames, fps)
        clip.detection_confidence = metrics_res.get("detection_confidence", 0.0)
        raw_metrics = metrics_res.get("metrics", {})
        clip.metrics_json = metrics_res

        if metrics_res.get("low_confidence") or not raw_metrics:
            clip.risk_level = "baseline_building"
            clip.form_score = 75.0
            clip.baseline_deltas_json = {}
            clip.findings_json = [
                {
                    "metric": "camera_framing",
                    "severity": "amber",
                    "title_en": "Low landmark visibility — check side-view camera framing & lighting",
                    "title_ar": "وضوح المفاصل منخفض — يُرجى مراجعة زاوية التصوير الجانبية والإضاءة",
                    "z_score": 0.0,
                }
            ]
            clip.cue_en = (
                "Detection confidence was below threshold. Position the phone 3 to 5 meters perpendicular to the track lane "
                "in clear lighting so the full upper body and wheelchair or stride stay centered in frame."
            )
            clip.cue_ar = (
                "كانت دقة رصد المفاصل منخفضة. ضع الهاتف على مسافة 3 إلى 5 أمتار بشكل عمودي على المسار مع إضاءة جيدة "
                "لضمان ظهور الجزء العلوي والجسم كاملاً بوضوح."
            )
            clip.confidence_note_en = f"Confidence {int(clip.detection_confidence * 100)}% (re-record recommended)."
            clip.confidence_note_ar = f"الدقة {int(clip.detection_confidence * 100)}% (يُنصح بإعادة التصوير)."
            clip.ai_source = "template_fallback"
            clip.status = "completed"
            db.commit()
            return

        base_eval = evaluate_and_update_baseline(
            db, athlete.id, clip.module_type, raw_metrics, update_baseline=True
        )
        clip.risk_level = base_eval["risk_level"]
        clip.form_score = base_eval["form_score"]
        clip.baseline_deltas_json = base_eval["baseline_deltas"]
        clip.findings_json = base_eval["findings"]

        att_rows = get_athlete_attendances(db, athlete.id)
        load_summary = evaluate_athlete_load(att_rows, athlete.limb_load_type, clip)

        kf_paths = [settings.storage_dir / name for name in (clip.keyframe_filenames or [])]
        ai_res = generate_coaching_feedback(
            keyframe_paths=kf_paths,
            metrics=raw_metrics,
            baseline_deltas=base_eval["baseline_deltas"],
            findings=base_eval["findings"],
            ipc_class=athlete.ipc_class,
            module_type=clip.module_type,
            risk_level=base_eval["risk_level"],
            load_summary=load_summary,
            detection_confidence=clip.detection_confidence,
        )
        clip.cue_en = ai_res["cue_en"]
        clip.cue_ar = ai_res["cue_ar"]
        clip.confidence_note_en = ai_res["confidence_note_en"]
        clip.confidence_note_ar = ai_res["confidence_note_ar"]
        clip.ai_source = ai_res["ai_source"]
        clip.status = "completed"
        db.commit()

        refresh_scout_summary_from_safe_view(db, athlete)
    except Exception as exc:
        clip = db.get(FormClip, clip_id)
        if clip:
            clip.status = "failed"
            clip.error_message = str(exc)
            db.commit()
    finally:
        db.close()


def _resolve_athlete_for_user(db: Session, user: User, athlete_id: int | None) -> AthleteProfile:
    if user.role == "athlete":
        if not user.athlete_profile:
            raise HTTPException(status_code=404, detail="Athlete profile not found")
        if athlete_id is not None and athlete_id != user.athlete_profile.id:
            raise HTTPException(status_code=403, detail="Cannot access another athlete's private clips")
        return user.athlete_profile
    if athlete_id is None:
        first = db.query(AthleteProfile).first()
        if not first:
            raise HTTPException(status_code=404, detail="No athletes found")
        return first
    athlete = db.get(AthleteProfile, athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return athlete


@router.post("/api/clips/upload", response_model=PrivateClipView)
async def upload_clip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    module_type: str = Form("wheelchair_propulsion"),
    athlete_id: int | None = Form(None),
    witness_badge: str = Form("self_submitted"),
    user: User = Depends(require_roles("athlete", "coach")),
    db: Session = Depends(get_db),
):
    if module_type not in ("wheelchair_propulsion", "standing_para_gait", "guide_runner_sync"):
        raise HTTPException(status_code=400, detail="Invalid module_type")
    athlete = _resolve_athlete_for_user(db, user, athlete_id)
    badge = "coach_witnessed" if user.role == "coach" else witness_badge

    ext = Path(file.filename or "clip.mp4").suffix.lower() or ".mp4"
    raw_name = f"upload_{athlete.id}_{uuid.uuid4().hex[:8]}{ext}"
    raw_path = settings.storage_dir / raw_name
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    raw_path.write_bytes(content)

    clip = FormClip(
        athlete_id=athlete.id,
        module_type=module_type,
        video_filename=raw_name,
        status="queued",
        witness_badge=badge,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)

    background_tasks.add_task(_run_clip_analysis, clip.id, raw_path)
    return serialize_private_clip(clip)


@router.post("/api/clips/analyze-demo", response_model=PrivateClipView)
def analyze_demo_clip(
    body: DemoClipAnalyzeRequest,
    user: User = Depends(require_roles("athlete", "coach")),
    db: Session = Depends(get_db),
):
    """Run real end-to-end analysis synchronously on a built-in side-view Para-Track clip for 1-click demos."""
    athlete = _resolve_athlete_for_user(db, user, body.athlete_id)
    fname = f"demo_{athlete.id}_{body.module_type}_{uuid.uuid4().hex[:6]}.mp4"
    out_path = settings.storage_dir / fname
    final_path, synthetic_frames = generate_synthetic_demo_clip(
        out_path, module_type=body.module_type, scenario=body.scenario
    )

    clip = FormClip(
        athlete_id=athlete.id,
        module_type=body.module_type,
        video_filename=final_path.name,
        overlay_filename=final_path.name,
        status="processing",
        witness_badge="coach_witnessed" if user.role == "coach" else body.witness_badge,
        is_demo_sample=True,
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)

    _run_clip_analysis(clip.id, final_path, precomputed_frames=synthetic_frames, fps=15.0)
    db.refresh(clip)
    return serialize_private_clip(clip)


@router.get("/api/clips/{clip_id}", response_model=PrivateClipView)
def get_clip(
    clip_id: int,
    user: User = Depends(require_roles("athlete", "coach")),
    db: Session = Depends(get_db),
):
    clip = db.get(FormClip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if user.role == "athlete" and (not user.athlete_profile or clip.athlete_id != user.athlete_profile.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return serialize_private_clip(clip)


@router.patch("/api/clips/{clip_id}/curate", response_model=PrivateClipView)
def toggle_curate(
    clip_id: int,
    curated: bool = True,
    user: User = Depends(require_roles("athlete", "coach")),
    db: Session = Depends(get_db),
):
    clip = db.get(FormClip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    if user.role == "athlete" and (not user.athlete_profile or clip.athlete_id != user.athlete_profile.id):
        raise HTTPException(status_code=403, detail="Forbidden")
    clip.is_curated_for_passport = curated
    db.commit()
    db.refresh(clip)
    return serialize_private_clip(clip)


@router.get("/api/media/{filename}")
def serve_media(filename: str):
    safe_name = Path(filename).name
    target = settings.storage_dir / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Media file not found")
    media_type = "video/mp4" if target.suffix.lower() == ".mp4" else "image/jpeg"
    return FileResponse(target, media_type=media_type)
