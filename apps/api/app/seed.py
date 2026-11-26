"""Seeded ATSN'26 demonstration dataset (explicitly labelled is_demo_data=True).

Includes the flagship proposal story:
- Tariq Al-Mansoor (IPC T54 Wheelchair Racer, 400m PB 50.84s awaiting coach verification,
  +34% upper-limb push spike + +11° shoulder elevation flag)
- Nimal Perera (IPC T64 Unilateral Blade Sprinter, 100m PB 11.42s, Coach-Verified)
- Layla Al-Harbi (IPC T12 Visually Impaired 800m Runner, Organizer-Verified + Guide-Runner Sync)
- Kavindu Silva (IPC T37 Ambulant CP 200m Runner, Organizer-Verified)
- Omar Haddad (IPC T40 Short-Stature 100m Sprinter, Baseline Building)
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import cv2
from sqlalchemy.orm import Session

from app.config import settings
from app.cv.pose import generate_synthetic_demo_clip
from app.load.acwr import compute_session_load
from app.models import (
    Achievement,
    AthleteBaseline,
    AthleteProfile,
    FormClip,
    SessionAttendance,
    TrainingSession,
    User,
)
from app.security import hash_password
from app.services.views import refresh_scout_summary_from_safe_view


def _ensure_seeded_clip_media(
    slug: str,
    module_type: str,
    scenario: str,
) -> tuple[str, list[str]]:
    mp4_name = f"seed_{slug}.mp4"
    mp4_path = settings.storage_dir / mp4_name
    kf_names = [f"seed_{slug}_kf_1.jpg", f"seed_{slug}_kf_2.jpg", f"seed_{slug}_kf_3.jpg"]
    if not mp4_path.exists() or not all((settings.storage_dir / k).exists() for k in kf_names):
        final_path, _ = generate_synthetic_demo_clip(
            mp4_path, module_type=module_type, scenario=scenario, duration_s=5.0, fps=15
        )
        cap = cv2.VideoCapture(str(final_path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 60)
        for ki, target_idx in enumerate([max(1, total // 5), total // 2, max(2, int(total * 0.8))]):
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
            ok, fr = cap.read()
            if ok:
                cv2.imwrite(str(settings.storage_dir / kf_names[ki]), fr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        cap.release()
    return mp4_name, kf_names


def seed_demo_data(db: Session) -> None:
    if db.query(User).count() > 0:
        return

    pw = hash_password("demo1234")
    now = datetime.now(UTC)
    today = date.today()

    # Coach & Scout accounts
    coach = User(
        email="coach@kinetiq.demo",
        password_hash=pw,
        full_name="Coach Dr. Samira Al-Kuwari",
        full_name_ar="المدربة د. سميرة الكواري",
        role="coach",
        country="Kuwait",
        affiliation="GCC & South Asia Para-Athletics Hub",
        affiliation_ar="مركز ألعاب القوى البارالمبية",
    )
    scout = User(
        email="scout@kinetiq.demo",
        password_hash=pw,
        full_name="Rohan Jayawardena (NPC Selector)",
        full_name_ar="روهان جاياواردينا (كشاف اللجنة البارالمبية)",
        role="scout",
        country="Sri Lanka",
        affiliation="National Paralympic Talent Committee",
        affiliation_ar="لجنة اختيار المواهب البارالمبية",
    )
    db.add_all([coach, scout])
    db.flush()

    # 1. Flagship T54 Wheelchair Racer (Demo Story)
    u_t54 = User(
        email="tariq.t54@kinetiq.demo",
        password_hash=pw,
        full_name="Tariq Al-Mansoor",
        full_name_ar="طارق المنصور",
        role="athlete",
        country="Kuwait",
        affiliation="KCST Para-Athletics Club",
        affiliation_ar="نادي كلية الكويت للعلوم والتكنولوجيا البارالمبي",
    )
    # 2. T64 Unilateral Blade Sprinter
    u_t64 = User(
        email="nimal.t64@kinetiq.demo",
        password_hash=pw,
        full_name="Nimal Perera",
        full_name_ar="نيمال بيريرا",
        role="athlete",
        country="Sri Lanka",
        affiliation="University of Moratuwa Para-Track",
        affiliation_ar="فريق جامعة موراتوا لألعاب القوى البارالمبية",
    )
    # 3. T12 Visually Impaired Runner
    u_t12 = User(
        email="layla.t12@kinetiq.demo",
        password_hash=pw,
        full_name="Layla Al-Harbi",
        full_name_ar="ليلى الحربي",
        role="athlete",
        country="Qatar",
        affiliation="Doha Inclusive Track Academy",
        affiliation_ar="أكاديمية الدوحة الشاملة لألعاب القوى",
    )
    # 4. T37 Ambulant CP Sprinter
    u_t37 = User(
        email="kavindu.t37@kinetiq.demo",
        password_hash=pw,
        full_name="Kavindu Silva",
        full_name_ar="كافيندو سيلفا",
        role="athlete",
        country="Sri Lanka",
        affiliation="Colombo Regional Para Club",
        affiliation_ar="نادي كولومبو الإقليمي البارالمبي",
    )
    # 5. T40 Short-Stature Sprinter (Baseline building)
    u_t40 = User(
        email="omar.t40@kinetiq.demo",
        password_hash=pw,
        full_name="Omar Haddad",
        full_name_ar="عمر حداد",
        role="athlete",
        country="Jordan",
        affiliation="Amman Para Athletics",
        affiliation_ar="ألعاب القوى البارالمبية عمّان",
    )
    db.add_all([u_t54, u_t64, u_t12, u_t37, u_t40])
    db.flush()

    ap_t54 = AthleteProfile(
        user_id=u_t54.id,
        coach_id=coach.id,
        ipc_class="T54",
        disability_category="wheelchair_racing",
        limb_load_type="upper_limb",
        primary_events=["100m", "400m", "800m"],
        passport_public=True,
        bio_en="IPC T54 wheelchair racer specializing in 400m and 800m track events. Demo profile for ATSN'26.",
        bio_ar="متسابق كراسي متحركة فئة T54 متخصص في سباقي 400 و800 متر. ملف تجريبي لمسابقة ATSN'26.",
        is_demo_data=True,
    )
    ap_t64 = AthleteProfile(
        user_id=u_t64.id,
        coach_id=coach.id,
        ipc_class="T64",
        disability_category="prosthetic_standing",
        limb_load_type="lower_limb",
        primary_events=["100m", "200m"],
        passport_public=True,
        bio_en="IPC T64 unilateral carbon-blade sprinter training for Asian Para Games qualification. Demo profile.",
        bio_ar="عدّاء فئة T64 بطرف صناعي كربوني يستعد للتأهل للألعاب البارالمبية الآسيوية. ملف تجريبي.",
        is_demo_data=True,
    )
    ap_t12 = AthleteProfile(
        user_id=u_t12.id,
        coach_id=coach.id,
        ipc_class="T12",
        disability_category="visual_impairment",
        limb_load_type="lower_limb",
        primary_events=["400m", "800m", "1500m"],
        passport_public=True,
        bio_en="IPC T12 visually impaired middle-distance runner utilizing voice-first Arabic & English coaching. Demo profile.",
        bio_ar="عدّاءة فئة T12 للمسافات المتوسطة تستخدم التدريب الصوتي باللغتين العربية والإنجليزية. ملف تجريبي.",
        is_demo_data=True,
    )
    ap_t37 = AthleteProfile(
        user_id=u_t37.id,
        coach_id=coach.id,
        ipc_class="T37",
        disability_category="cerebral_palsy_standing",
        limb_load_type="lower_limb",
        primary_events=["100m", "200m", "400m"],
        passport_public=True,
        bio_en="IPC T37 ambulant sprinter focusing on trunk stability and individualized fatigue thresholds. Demo profile.",
        bio_ar="عدّاء فئة T37 يركز على ثبات الجذع ومراقبة الإجهاد وفق خط أساسه الشخصي. ملف تجريبي.",
        is_demo_data=True,
    )
    ap_t40 = AthleteProfile(
        user_id=u_t40.id,
        coach_id=coach.id,
        ipc_class="T40",
        disability_category="short_stature",
        limb_load_type="lower_limb",
        primary_events=["100m", "200m"],
        passport_public=True,
        bio_en="IPC T40 short-stature sprinter building a limb-proportion-independent personal baseline. Demo profile.",
        bio_ar="عدّاء قصر القامة فئة T40 يبني خط أساس شخصي مستقل عن النسب القياسية. ملف تجريبي.",
        is_demo_data=True,
    )
    db.add_all([ap_t54, ap_t64, ap_t12, ap_t37, ap_t40])
    db.flush()

    # Seed personal baselines (3+ historical clips for T54, T64, T12, T37; only 1 for T40)
    baselines = [
        # Tariq T54 baseline (normal shoulder elevation ~11.5°; current fatigue clip ~22.5° => +11.0° delta!)
        AthleteBaseline(athlete_id=ap_t54.id, module_type="wheelchair_propulsion", metric_name="shoulder_elevation_deg", values_history=[11.0, 11.5, 12.0, 11.4], median_val=11.5, mad_val=0.45, sample_count=4),
        AthleteBaseline(athlete_id=ap_t54.id, module_type="wheelchair_propulsion", metric_name="trunk_lean_deg", values_history=[37.5, 38.0, 38.5, 37.8], median_val=37.9, mad_val=0.35, sample_count=4),
        AthleteBaseline(athlete_id=ap_t54.id, module_type="wheelchair_propulsion", metric_name="elbow_contact_deg", values_history=[106.0, 108.0, 107.0, 107.5], median_val=107.2, mad_val=0.7, sample_count=4),
        AthleteBaseline(athlete_id=ap_t54.id, module_type="wheelchair_propulsion", metric_name="push_cadence_spm", values_history=[108.0, 110.0, 111.0, 109.5], median_val=109.8, mad_val=1.0, sample_count=4),
        AthleteBaseline(athlete_id=ap_t54.id, module_type="wheelchair_propulsion", metric_name="stroke_arc_norm", values_history=[58.0, 59.5, 60.0, 59.0], median_val=59.2, mad_val=0.6, sample_count=4),
        # Nimal T64
        AthleteBaseline(athlete_id=ap_t64.id, module_type="standing_para_gait", metric_name="trunk_lean_deg", values_history=[12.0, 12.5, 11.8, 12.2], median_val=12.1, mad_val=0.3, sample_count=4),
        AthleteBaseline(athlete_id=ap_t64.id, module_type="standing_para_gait", metric_name="intact_knee_flexion_deg", values_history=[44.0, 45.2, 44.6, 44.8], median_val=44.7, mad_val=0.4, sample_count=4),
        AthleteBaseline(athlete_id=ap_t64.id, module_type="standing_para_gait", metric_name="pelvic_oscillation_norm", values_history=[8.5, 8.8, 8.4, 8.6], median_val=8.6, mad_val=0.2, sample_count=4),
        AthleteBaseline(athlete_id=ap_t64.id, module_type="standing_para_gait", metric_name="stride_cadence_spm", values_history=[176.0, 178.0, 175.0, 177.0], median_val=176.5, mad_val=1.0, sample_count=4),
        # Layla T12 (Guide Sync)
        AthleteBaseline(athlete_id=ap_t12.id, module_type="guide_runner_sync", metric_name="trunk_lean_deg", values_history=[11.5, 11.8, 12.0, 11.7], median_val=11.75, mad_val=0.2, sample_count=4),
        AthleteBaseline(athlete_id=ap_t12.id, module_type="guide_runner_sync", metric_name="guide_stride_sync_pct", values_history=[93.0, 94.5, 92.8, 93.8], median_val=93.4, mad_val=0.6, sample_count=4),
        AthleteBaseline(athlete_id=ap_t12.id, module_type="guide_runner_sync", metric_name="tether_spacing_variability", values_history=[4.2, 4.5, 4.0, 4.3], median_val=4.25, mad_val=0.2, sample_count=4),
        # Kavindu T37
        AthleteBaseline(athlete_id=ap_t37.id, module_type="standing_para_gait", metric_name="trunk_lean_deg", values_history=[15.2, 15.8, 15.0, 15.5], median_val=15.35, mad_val=0.3, sample_count=4),
    ]
    db.add_all(baselines)

    # Seed 4 weeks of squad sessions:
    # For Tariq (upper_limb): steady weeks W-3..W-1 (~1100 load/week), then Current Week spikes +35% (~1520, ACWR ~1.58 RED)
    def add_sess(days_ago: int, title: str, group: str, limb: str, dur: float, dist: float, rpe: float, athlete_ids: list[int]):
        s = TrainingSession(
            coach_id=coach.id,
            title=title,
            event_group=group,
            limb_load_type=limb,
            session_date=today - timedelta(days=days_ago),
            duration_min=dur,
            distance_m=dist,
            intensity_rpe=rpe,
            computed_load=compute_session_load(limb, dur, dist, rpe),
        )
        db.add(s)
        db.flush()
        for aid in athlete_ids:
            db.add(SessionAttendance(session_id=s.id, athlete_id=aid, attended=True, coach_confirmed=True))

    # Upper-limb (Wheelchair T54) history
    for d in (25, 22, 19, 17, 15, 12, 10, 8):
        add_sess(d, "T54 Aerobic Push Endurance", "Wheelchair T51-T54", "upper_limb", 45, 2400, 6.5, [ap_t54.id])
    # Acute week spike for Tariq T54
    add_sess(5, "T54 Race-Pace Intervals (6 × 200m)", "Wheelchair T51-T54", "upper_limb", 60, 3200, 8.5, [ap_t54.id])
    add_sess(3, "T54 Speed Endurance (4 × 400m)", "Wheelchair T51-T54", "upper_limb", 65, 3600, 9.0, [ap_t54.id])
    add_sess(1, "Pre-Championship Push Block (6 × 200m + 4 × 400m)", "Wheelchair T51-T54", "upper_limb", 65, 3800, 9.0, [ap_t54.id])

    # Lower-limb (Standing / Prosthetic / VI) steady sessions
    for d in (24, 21, 17, 14, 10, 7, 4, 2):
        add_sess(d, "Standing Para-Track Tempo & Stride Mechanics", "Standing T11-T64", "lower_limb", 45, 1800, 7.0, [ap_t64.id, ap_t12.id, ap_t37.id, ap_t40.id])
    # Slight amber bump for Kavindu T37
    add_sess(1, "T37 Acceleration Blocks (8 × 120m)", "Standing T35-T38", "lower_limb", 50, 2200, 8.5, [ap_t37.id])

    # Generate real playable seeded overlay clips & keyframes
    t54_mp4, t54_kfs = _ensure_seeded_clip_media("tariq_t54_fatigue", "wheelchair_propulsion", "fatigue_spike")
    t54_base_mp4, t54_base_kfs = _ensure_seeded_clip_media("tariq_t54_base", "wheelchair_propulsion", "optimal_baseline")
    t64_mp4, t64_kfs = _ensure_seeded_clip_media("nimal_t64_gait", "standing_para_gait", "optimal_baseline")
    t12_mp4, t12_kfs = _ensure_seeded_clip_media("layla_t12_guide", "guide_runner_sync", "optimal_baseline")

    clips = [
        # Historical baseline clip for Tariq (10 days ago)
        FormClip(
            athlete_id=ap_t54.id,
            module_type="wheelchair_propulsion",
            video_filename=t54_base_mp4,
            overlay_filename=t54_base_mp4,
            keyframe_filenames=t54_base_kfs,
            status="completed",
            witness_badge="coach_witnessed",
            recorded_at=now - timedelta(days=10),
            detection_confidence=0.93,
            form_score=91.0,
            metrics_json={"metrics": {"shoulder_elevation_deg": 11.4, "trunk_lean_deg": 37.8, "elbow_contact_deg": 107.5, "push_cadence_spm": 109.5, "stroke_arc_norm": 59.0}},
            baseline_deltas_json={},
            risk_level="green",
            findings_json=[],
            cue_en="Clean push-rim rhythm aligned with your T54 personal baseline.",
            cue_ar="إيقاع دفع متوازن ومتوافق مع خط أساسك الشخصي لفئة T54.",
            confidence_note_en="Side-view landmark confidence: 93%.",
            confidence_note_ar="دقة تتبع المفاصل الجانبية: 93%.",
            ai_source="cached",
            is_curated_for_passport=True,
            is_demo_sample=True,
        ),
        # Current flagged clip for Tariq (+11° shoulder elevation, Red risk)
        FormClip(
            athlete_id=ap_t54.id,
            module_type="wheelchair_propulsion",
            video_filename=t54_mp4,
            overlay_filename=t54_mp4,
            keyframe_filenames=t54_kfs,
            status="completed",
            witness_badge="coach_witnessed",
            recorded_at=now - timedelta(hours=6),
            detection_confidence=0.94,
            form_score=87.5,
            metrics_json={"metrics": {"shoulder_elevation_deg": 22.5, "trunk_lean_deg": 44.0, "elbow_contact_deg": 99.0, "push_cadence_spm": 99.0, "stroke_arc_norm": 51.2}},
            baseline_deltas_json={
                "shoulder_elevation_deg": {"current": 22.5, "baseline_median": 11.5, "delta": 11.0, "delta_display": "+11.0° vs personal baseline", "z_score": 4.4, "unit": "°", "status": "red", "sample_count": 4, "label_en": "Shoulder recovery elevation", "label_ar": "ارتفاع الكتف أثناء الاسترجاع"},
                "trunk_lean_deg": {"current": 44.0, "baseline_median": 37.9, "delta": 6.1, "delta_display": "+6.1° vs personal baseline", "z_score": 2.03, "unit": "°", "status": "amber", "sample_count": 4, "label_en": "Trunk forward lean", "label_ar": "ميلان الجذع للأمام"},
                "push_cadence_spm": {"current": 99.0, "baseline_median": 109.8, "delta": -10.8, "delta_display": "-10.8 spm vs personal baseline", "z_score": -1.8, "unit": " spm", "status": "green", "sample_count": 4, "label_en": "Push cadence", "label_ar": "إيقاع الدفع"},
            },
            risk_level="red",
            findings_json=[
                {"metric": "shoulder_elevation_deg", "severity": "red", "title_en": "Elevated right shoulder recovery (+11.0° vs personal baseline) — early rotator-cuff fatigue risk", "title_ar": "ارتفاع الكتف الأيمن أثناء الاسترجاع (+11.0° عن خط الأساس الشخصي) — مؤشر إجهاد مبكر للكفة المدورة", "z_score": 4.4},
                {"metric": "trunk_lean_deg", "severity": "amber", "title_en": "Increased trunk forward lean (+6.1° vs personal baseline)", "title_ar": "زيادة ميلان الجذع للأمام (+6.1° عن خط الأساس الشخصي)", "z_score": 2.03},
            ],
            cue_en="Risk indicator for T54: your right shoulder rose 11 degrees higher than your personal baseline during push-rim recovery after a sharp weekly volume jump. Relax your shoulders downward on recovery, reduce your next high-intensity push session by 20 percent, and consult a qualified sports physiotherapist if shoulder tightness persists.",
            cue_ar="مؤشر انتباه لفئة T54: ارتفع كتفك الأيمن بمقدار 11 درجة فوق خط أساسك الشخصي أثناء مرحلة الاسترجاع بعد ارتفاع حاد في أحمال الدفع الأسبوعية. حافظ على استرخاء الكتفين للأسفل، خفّض حصة الدفع القادمة بنسبة 20%، واستشر أخصائي علاج طبيعي رياضي إذا استمر الشد.",
            confidence_note_en="Side-view landmark confidence: 94%. Coaching risk indicator only — not medical diagnosis.",
            confidence_note_ar="دقة تتبع المفاصل الجانبية: 94%. مؤشر تدريبي فقط وليس تشخيصاً طبياً.",
            ai_source="cached",
            is_curated_for_passport=True,
            is_demo_sample=True,
        ),
        # Nimal T64 optimal clip
        FormClip(
            athlete_id=ap_t64.id,
            module_type="standing_para_gait",
            video_filename=t64_mp4,
            overlay_filename=t64_mp4,
            keyframe_filenames=t64_kfs,
            status="completed",
            witness_badge="coach_witnessed",
            recorded_at=now - timedelta(days=2),
            detection_confidence=0.92,
            form_score=93.0,
            metrics_json={"intact_side_tracked": "right", "prosthetic_landmark_policy": "excluded_by_design_gemini_keyframe_verified", "metrics": {"trunk_lean_deg": 12.2, "intact_knee_flexion_deg": 45.0, "pelvic_oscillation_norm": 8.5, "stride_cadence_spm": 177.0}},
            baseline_deltas_json={
                "trunk_lean_deg": {"current": 12.2, "baseline_median": 12.1, "delta": 0.1, "delta_display": "+0.1° vs personal baseline", "z_score": 0.03, "unit": "°", "status": "green", "sample_count": 4, "label_en": "Trunk forward lean", "label_ar": "ميلان الجذع للأمام"},
                "intact_knee_flexion_deg": {"current": 45.0, "baseline_median": 44.7, "delta": 0.3, "delta_display": "+0.3° vs personal baseline", "z_score": 0.08, "unit": "°", "status": "green", "sample_count": 4, "label_en": "Intact-limb knee flexion", "label_ar": "ثني الركبة للطرف السليم"},
            },
            risk_level="green",
            findings_json=[],
            cue_en="Strong T64 consistency: intact-limb knee flexion and trunk angle stay tightly aligned with your personal baseline, with blade clearance verified from keyframes.",
            cue_ar="ثبات ممتاز لفئة T64: زاوية الجذع وثني الركبة للطرف السليم متوافقان بدقة مع خط أساسك الشخصي، وتم التحقق من استقامة الشفرة الكربونية عبر الإطارات الرئيسية.",
            confidence_note_en="Intact-limb confidence: 92%. Prosthetic blade verified visually, never scored by able-bodied leg norms.",
            confidence_note_ar="دقة تتبع الطرف السليم: 92%. تم فحص الشفرة الكربونية بصرياً دون مقارنتها بمعايير غير مخصصة.",
            ai_source="cached",
            is_curated_for_passport=True,
            is_demo_sample=True,
        ),
        # Layla T12 Guide-Runner Sync clip
        FormClip(
            athlete_id=ap_t12.id,
            module_type="guide_runner_sync",
            video_filename=t12_mp4,
            overlay_filename=t12_mp4,
            keyframe_filenames=t12_kfs,
            status="completed",
            witness_badge="coach_witnessed",
            recorded_at=now - timedelta(days=3),
            detection_confidence=0.91,
            form_score=94.5,
            metrics_json={"dual_pose_detected": True, "metrics": {"trunk_lean_deg": 11.9, "guide_stride_sync_pct": 94.2, "tether_spacing_variability": 4.1, "stride_cadence_spm": 182.0}},
            baseline_deltas_json={
                "guide_stride_sync_pct": {"current": 94.2, "baseline_median": 93.4, "delta": 0.8, "delta_display": "+0.8% vs personal baseline", "z_score": 0.2, "unit": "%", "status": "green", "sample_count": 4, "label_en": "Guide-runner stride sync", "label_ar": "تزامن الخطوة مع المرشد"},
            },
            risk_level="green",
            findings_json=[],
            cue_en="Excellent T12 guide-runner synchronization at 94 percent stride phase alignment with steady tether spacing. Keep using short verbal cadence cues entering the final curve.",
            cue_ar="تزامن ممتاز لفئة T12 مع المرشد بنسبة 94% وثبات في مسافة حبل التوجيه. استمري باستخدام الإشارات الصوتية القصيرة عند دخول المنعطف الأخير.",
            confidence_note_en="Dual-pose landmark confidence: 91%. Audio-first coaching ready.",
            confidence_note_ar="دقة تتبع العداء والمرشد: 91%. التدريب الصوتي جاهز.",
            ai_source="cached",
            is_curated_for_passport=True,
            is_demo_sample=True,
        ),
        # Kavindu T37 outdated clip (>14 days old to demonstrate freshness decay!)
        FormClip(
            athlete_id=ap_t37.id,
            module_type="standing_para_gait",
            video_filename=t64_mp4,
            overlay_filename=t64_mp4,
            keyframe_filenames=t64_kfs,
            status="completed",
            witness_badge="self_submitted",
            recorded_at=now - timedelta(days=19),
            detection_confidence=0.88,
            form_score=86.0,
            metrics_json={"metrics": {"trunk_lean_deg": 15.6, "stride_cadence_spm": 168.0}},
            baseline_deltas_json={},
            risk_level="green",
            findings_json=[],
            cue_en="Previous T37 checkpoint was stable, but this clip is 19 days old. Upload a fresh 10-second side-view clip before peak trials.",
            cue_ar="كان الفحص السابق لفئة T37 مستقراً لكنه أقدم من 14 يوماً. يُنصح برفع مقطع جديد مدته 10 ثوانٍ قبل التجارب.",
            confidence_note_en="Clip is >14 days old (freshness weight decayed).",
            confidence_note_ar="المقطع أقدم من 14 يوماً (تم تخفيض وزنه تلقائياً).",
            ai_source="cached",
            is_curated_for_passport=True,
            is_demo_sample=True,
        ),
    ]
    db.add_all(clips)

    # Seed Achievements (including Tariq's 50.84s 400m PB ready for live Coach verification in Demo Step 4!)
    achievements = [
        Achievement(
            athlete_id=ap_t54.id,
            event_name="400m",
            ipc_class="T54",
            result_value="50.84s",
            result_seconds=50.84,
            competition_name="National Para Athletics Championship 2026 (Demo)",
            achieved_date=today - timedelta(days=14),
            proof_reference="official_scorecard_t54_400m.pdf",
            verification_tier="self_reported",  # Ready for 1-click Coach Verification in Demo Step 4!
            is_pb=True,
        ),
        Achievement(
            athlete_id=ap_t54.id,
            event_name="800m",
            ipc_class="T54",
            result_value="1:41.20",
            result_seconds=101.20,
            competition_name="GCC Wheelchair Track Open 2026 (Demo)",
            achieved_date=today - timedelta(days=45),
            proof_reference="gcc_open_2026_results.pdf",
            verification_tier="organizer_verified",
            verified_by_id=coach.id,
            verified_at=now - timedelta(days=40),
            is_pb=True,
        ),
        Achievement(
            athlete_id=ap_t64.id,
            event_name="100m",
            ipc_class="T64",
            result_value="11.42s",
            result_seconds=11.42,
            competition_name="Sri Lanka National Para Trials 2026 (Demo)",
            achieved_date=today - timedelta(days=28),
            proof_reference="sl_para_trials_100m.pdf",
            verification_tier="coach_verified",
            verified_by_id=coach.id,
            verified_at=now - timedelta(days=25),
            is_pb=True,
        ),
        Achievement(
            athlete_id=ap_t12.id,
            event_name="800m",
            ipc_class="T12",
            result_value="2:14.65",
            result_seconds=134.65,
            competition_name="West Asia Para Grand Prix 2026 (Demo)",
            achieved_date=today - timedelta(days=35),
            proof_reference="wpa_grand_prix_doha.pdf",
            verification_tier="organizer_verified",
            verified_by_id=coach.id,
            verified_at=now - timedelta(days=32),
            is_pb=True,
        ),
        Achievement(
            athlete_id=ap_t37.id,
            event_name="200m",
            ipc_class="T37",
            result_value="24.90s",
            result_seconds=24.90,
            competition_name="Inter-University Inclusive Meet 2026 (Demo)",
            achieved_date=today - timedelta(days=50),
            proof_reference="inter_uni_para_200m.pdf",
            verification_tier="coach_verified",
            verified_by_id=coach.id,
            verified_at=now - timedelta(days=48),
            is_pb=True,
        ),
        Achievement(
            athlete_id=ap_t40.id,
            event_name="100m",
            ipc_class="T40",
            result_value="16.45s",
            result_seconds=16.45,
            competition_name="Amman Regional Track Festival 2026 (Demo)",
            achieved_date=today - timedelta(days=20),
            proof_reference="amman_festival_sheet.pdf",
            verification_tier="coach_verified",
            verified_by_id=coach.id,
            verified_at=now - timedelta(days=18),
            is_pb=True,
        ),
    ]
    db.add_all(achievements)
    db.commit()

    # Generate initial scout-safe bilingual summaries for all seeded athletes
    for ap in (ap_t54, ap_t64, ap_t12, ap_t37, ap_t40):
        refresh_scout_summary_from_safe_view(db, ap)
