"""Per-athlete self-baseline drift scoring (Median & MAD robust z-score).

Never scores a Para-athlete against able-bodied textbook norms.
Athletes with < 3 baseline samples receive `baseline_building` instead of false alerts.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.models import AthleteBaseline

METRIC_LABELS = {
    "shoulder_elevation_deg": ("Shoulder recovery elevation", "ارتفاع الكتف أثناء الاسترجاع", "°", "higher_is_risk"),
    "trunk_lean_deg": ("Trunk forward lean", "ميلان الجذع للأمام", "°", "deviation_is_risk"),
    "elbow_contact_deg": ("Elbow push-rim contact angle", "زاوية المرفق عند ملامسة الإطار", "°", "deviation_is_risk"),
    "push_cadence_spm": ("Push cadence", "إيقاع الدفع", " spm", "lower_is_risk"),
    "stroke_arc_norm": ("Push-rim stroke arc", "قوس الدفع على الإطار", "%", "lower_is_risk"),
    "intact_knee_flexion_deg": ("Intact-limb knee flexion", "ثني الركبة للطرف السليم", "°", "deviation_is_risk"),
    "pelvic_oscillation_norm": ("Pelvic vertical oscillation", "تذبذب الحوض العمودي", "%", "higher_is_risk"),
    "stride_cadence_spm": ("Stride cadence", "إيقاع الخطوة", " spm", "lower_is_risk"),
    "guide_stride_sync_pct": ("Guide-runner stride sync", "تزامن الخطوة مع المرشد", "%", "lower_is_risk"),
    "tether_spacing_variability": ("Tether spacing drift", "تباين مسافة الحبل مع المرشد", "%", "higher_is_risk"),
}

MIN_BASELINE_SAMPLES = 3
MIN_SIGMA = {
    "shoulder_elevation_deg": 2.5,
    "trunk_lean_deg": 3.0,
    "elbow_contact_deg": 5.0,
    "push_cadence_spm": 6.0,
    "stroke_arc_norm": 4.0,
    "intact_knee_flexion_deg": 4.0,
    "pelvic_oscillation_norm": 3.5,
    "stride_cadence_spm": 6.0,
    "guide_stride_sync_pct": 4.0,
    "tether_spacing_variability": 3.0,
}


def evaluate_and_update_baseline(
    db: Session,
    athlete_id: int,
    module_type: str,
    metrics: dict[str, float],
    update_baseline: bool = True,
) -> dict:
    """Compare current clip metrics against athlete's own median/MAD baseline."""
    existing = {
        b.metric_name: b
        for b in db.query(AthleteBaseline)
        .filter_by(athlete_id=athlete_id, module_type=module_type)
        .all()
    }

    deltas: dict[str, dict] = {}
    findings: list[dict] = []
    max_risk_z = 0.0
    baseline_ready = True

    for metric_name, val in metrics.items():
        val = float(val)
        rec = existing.get(metric_name)
        label_en, label_ar, unit, direction = METRIC_LABELS.get(
            metric_name, (metric_name.replace("_", " ").title(), metric_name, "", "deviation_is_risk")
        )

        if rec is None or rec.sample_count < MIN_BASELINE_SAMPLES:
            baseline_ready = False
            deltas[metric_name] = {
                "current": round(val, 1),
                "baseline_median": round(rec.median_val, 1) if rec else round(val, 1),
                "delta": 0.0,
                "z_score": 0.0,
                "unit": unit,
                "status": "baseline_building",
                "sample_count": (rec.sample_count if rec else 0) + (1 if update_baseline else 0),
                "label_en": label_en,
                "label_ar": label_ar,
            }
        else:
            delta = round(val - rec.median_val, 1)
            sigma = max(1.4826 * rec.mad_val, MIN_SIGMA.get(metric_name, 2.5))
            z = round(delta / sigma, 2)

            # Determine risk-oriented z magnitude
            if direction == "higher_is_risk":
                risk_z = max(0.0, z)
            elif direction == "lower_is_risk":
                risk_z = max(0.0, -z)
            else:
                risk_z = abs(z)

            max_risk_z = max(max_risk_z, risk_z)
            status = "red" if risk_z >= 2.8 else ("amber" if risk_z >= 2.0 else "green")
            sign = "+" if delta >= 0 else ""

            deltas[metric_name] = {
                "current": round(val, 1),
                "baseline_median": round(rec.median_val, 1),
                "delta": delta,
                "delta_display": f"{sign}{delta}{unit} vs personal baseline",
                "z_score": z,
                "unit": unit,
                "status": status,
                "sample_count": rec.sample_count,
                "label_en": label_en,
                "label_ar": label_ar,
            }

            if status in ("amber", "red"):
                findings.append(
                    {
                        "metric": metric_name,
                        "severity": status,
                        "title_en": f"{label_en} ({sign}{delta}{unit} vs personal baseline)",
                        "title_ar": f"{label_ar} ({sign}{delta}{unit} مقارنة بخط الأساس الشخصي)",
                        "z_score": z,
                    }
                )

        if update_baseline:
            if rec is None:
                rec = AthleteBaseline(
                    athlete_id=athlete_id,
                    module_type=module_type,
                    metric_name=metric_name,
                    values_history=[round(val, 2)],
                    median_val=round(val, 2),
                    mad_val=0.0,
                    sample_count=1,
                )
                db.add(rec)
            else:
                # Only fold non-extreme clips into long-term baseline so an acute fatigue spike doesn't corrupt baseline
                current_z = abs(deltas[metric_name]["z_score"])
                if rec.sample_count < MIN_BASELINE_SAMPLES or current_z < 2.5:
                    hist = list(rec.values_history or [])[-19:] + [round(val, 2)]
                    arr = np.array(hist, dtype=float)
                    med = float(np.median(arr))
                    mad = float(np.median(np.abs(arr - med)))
                    rec.values_history = hist
                    rec.median_val = round(med, 2)
                    rec.mad_val = round(mad, 2)
                    rec.sample_count = len(hist)

    if not baseline_ready:
        risk_level = "baseline_building"
        form_score = 84.0
    elif max_risk_z >= 2.8:
        risk_level = "red"
        form_score = round(max(52.0, 88.0 - max_risk_z * 7.5), 1)
    elif max_risk_z >= 2.0:
        risk_level = "amber"
        form_score = round(max(68.0, 92.0 - max_risk_z * 6.0), 1)
    else:
        risk_level = "green"
        form_score = round(min(96.0, 93.0 - max_risk_z * 2.5), 1)

    return {
        "risk_level": risk_level,
        "form_score": form_score,
        "baseline_deltas": deltas,
        "findings": findings,
    }
