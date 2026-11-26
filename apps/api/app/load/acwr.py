from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Iterable

from app.models import FormClip, SessionAttendance, TrainingSession


def compute_session_load(
    limb_load_type: str,
    duration_min: float,
    distance_m: float,
    intensity_rpe: float,
) -> float:
    """Compute transparent session workload units.

    - Upper-limb (wheelchair racing): duration_min * intensity_rpe, with a small
      distance bonus when track push distance is provided.
    - Lower-limb (standing/prosthetic/VI running): (distance_m / 100) * intensity_rpe
      when distance is logged, otherwise duration_min * intensity_rpe.
    """
    rpe = max(1.0, min(10.0, float(intensity_rpe)))
    if limb_load_type == "upper_limb":
        base = max(duration_min, 10.0) * rpe
        if distance_m > 0:
            base += (distance_m / 400.0) * rpe * 2.5
        return round(base, 1)

    if distance_m > 0:
        return round((distance_m / 100.0) * rpe * 1.5, 1)
    return round(max(duration_min, 10.0) * rpe, 1)


def clip_freshness(clip: FormClip | None, now: datetime | None = None) -> dict:
    """14-day freshness window with exponential decay weighting."""
    if clip is None:
        return {
            "days_old": None,
            "freshness_weight": 0.0,
            "status": "no_clip",
            "label_en": "No clip screened yet",
            "label_ar": "لم يتم فحص أي مقطع بعد",
        }
    ref = now or datetime.now(UTC)
    rec = clip.recorded_at
    if rec.tzinfo is None:
        rec = rec.replace(tzinfo=UTC)
    days_old = max(0, (ref - rec).days)
    if days_old <= 14:
        weight = round(1.0 - (days_old / 28.0), 2)
        return {
            "days_old": days_old,
            "freshness_weight": weight,
            "status": "fresh",
            "label_en": f"Fresh ({days_old}d ago)",
            "label_ar": f"حديث (منذ {days_old} يوم)",
        }
    weight = round(max(0.15, 0.5 * (0.9 ** (days_old - 14))), 2)
    return {
        "days_old": days_old,
        "freshness_weight": weight,
        "status": "outdated",
        "label_en": f"Outdated ({days_old}d ago) — re-check recommended",
        "label_ar": f"قديم (منذ {days_old} يوم) — يُنصح بإعادة الفحص",
    }


def evaluate_athlete_load(
    attendances: Iterable[tuple[SessionAttendance, TrainingSession]],
    limb_load_type: str,
    latest_clip: FormClip | None = None,
    reference_date: date | None = None,
) -> dict:
    """Compute 7-day acute vs 28-day chronic workload (ACWR), WoW % jump, zone, and readiness."""
    today = reference_date or date.today()
    acute_start = today - timedelta(days=6)
    prev_week_start = today - timedelta(days=13)
    prev_week_end = today - timedelta(days=7)
    chronic_start = today - timedelta(days=27)

    acute_7d = 0.0
    prev_7d = 0.0
    chronic_28d_total = 0.0
    sessions_30d = 0
    weekly_series = [0.0, 0.0, 0.0, 0.0]  # W-3, W-2, W-1, Current W

    for att, sess in attendances:
        if not att.attended:
            continue
        if sess.limb_load_type != limb_load_type:
            continue
        days_ago = (today - sess.session_date).days
        if days_ago < 0 or days_ago > 30:
            continue
        sessions_30d += 1
        load = float(sess.computed_load)
        if sess.session_date >= acute_start:
            acute_7d += load
        if prev_week_start <= sess.session_date <= prev_week_end:
            prev_7d += load
        if sess.session_date >= chronic_start:
            chronic_28d_total += load
            bucket = 3 - min(3, days_ago // 7)
            weekly_series[bucket] += load

    chronic_weekly_avg = chronic_28d_total / 4.0 if chronic_28d_total > 0 else 0.0
    if chronic_weekly_avg > 0:
        acwr = round(acute_7d / chronic_weekly_avg, 2)
    else:
        acwr = 1.0 if acute_7d == 0 else 1.5

    if prev_7d > 0:
        wow_change_pct = round(((acute_7d - prev_7d) / prev_7d) * 100.0, 1)
    elif acute_7d > 0:
        wow_change_pct = 100.0
    else:
        wow_change_pct = 0.0

    if acwr > 1.5 or wow_change_pct >= 30.0:
        load_zone = "red"
    elif acwr >= 1.3 or wow_change_pct >= 20.0:
        load_zone = "amber"
    else:
        load_zone = "green"

    fresh = clip_freshness(latest_clip)
    clip_risk = latest_clip.risk_level if latest_clip and latest_clip.status == "completed" else "baseline_building"
    clip_weight = fresh["freshness_weight"]

    # Combined readiness score (0-100, higher is safer/more ready)
    readiness = 92
    if load_zone == "red":
        readiness -= 34
    elif load_zone == "amber":
        readiness -= 16

    if clip_risk == "red":
        readiness -= int(24 * max(0.35, clip_weight))
    elif clip_risk == "amber":
        readiness -= int(12 * max(0.35, clip_weight))

    readiness = max(18, min(98, readiness))

    limb_label_en = "upper-limb push" if limb_load_type == "upper_limb" else "lower-limb track"
    limb_label_ar = "دفع الطرف العلوي (الكرسي المتحرك)" if limb_load_type == "upper_limb" else "أحمال الجري للطرف السفلي"

    reasons_en: list[str] = []
    reasons_ar: list[str] = []
    if load_zone == "red":
        reasons_en.append(f"+{wow_change_pct:.0f}% weekly {limb_label_en} spike (ACWR {acwr:.2f})")
        reasons_ar.append(f"ارتفاع مفاجئ بنسبة +{wow_change_pct:.0f}% في أحمال {limb_label_ar} (نسبة الحمل {acwr:.2f})")
    elif load_zone == "amber":
        reasons_en.append(f"Elevated {limb_label_en} volume (+{wow_change_pct:.0f}% WoW, ACWR {acwr:.2f})")
        reasons_ar.append(f"ارتفاع ملحوظ في أحمال {limb_label_ar} (+{wow_change_pct:.0f}% أسبوعياً)")
    else:
        reasons_en.append(f"Stable {limb_label_en} workload (ACWR {acwr:.2f})")
        reasons_ar.append(f"أحمال {limb_label_ar} مستقرة (نسبة الحمل {acwr:.2f})")

    if latest_clip and latest_clip.findings_json:
        top = latest_clip.findings_json[0]
        if isinstance(top, dict):
            if top.get("title_en"):
                reasons_en.append(top["title_en"])
            if top.get("title_ar"):
                reasons_ar.append(top["title_ar"])

    if fresh["status"] == "outdated":
        reasons_en.append("Clip >14d old (down-weighted)")
        reasons_ar.append("مقطع الفحص أقدم من 14 يوماً (وزن مخفض)")

    overall_zone = load_zone
    if clip_risk == "red" and fresh["status"] == "fresh":
        overall_zone = "red"
    elif clip_risk == "amber" and overall_zone == "green" and fresh["status"] == "fresh":
        overall_zone = "amber"

    return {
        "limb_load_type": limb_load_type,
        "acute_load_7d": round(acute_7d, 1),
        "chronic_weekly_avg_28d": round(chronic_weekly_avg, 1),
        "acwr": acwr,
        "wow_change_pct": wow_change_pct,
        "load_zone": load_zone,
        "overall_zone": overall_zone,
        "readiness_score": readiness,
        "sessions_30d": sessions_30d,
        "weekly_series": [round(x, 1) for x in weekly_series],
        "clip_freshness": fresh,
        "combined_reason_en": " + ".join(reasons_en),
        "combined_reason_ar": " + ".join(reasons_ar),
    }
