"""Multimodal Gemini service (EN/AR coaching, scout-safe summaries, NL scout search) + fallbacks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from google import genai
from google.genai import types

from app.config import settings


def _get_client() -> genai.Client | None:
    if not settings.gemini_api_key:
        return None
    return genai.Client(api_key=settings.gemini_api_key)


def _template_coaching(
    module_type: str,
    ipc_class: str,
    risk_level: str,
    findings: list[dict],
    load_summary: dict,
    detection_confidence: float,
) -> dict:
    load_zone = load_summary.get("load_zone", "green")
    wow = load_summary.get("wow_change_pct", 0.0)

    if risk_level == "baseline_building":
        cue_en = (
            f"Personal baseline calibration recorded for IPC class {ipc_class}. "
            "Upload 2 more side-view clips so KinetiQ Para can track your individual movement drift without comparing you to able-bodied norms."
        )
        cue_ar = (
            f"تم تسجيل مقطع المعايرة لخط الأساس الشخصي لفئة {ipc_class}. "
            "ارفع مقطعين إضافيين بزاوية جانبية ليتمكن التطبيق من متابعة توازن حركتك الشخصية بدقة دون مقارنتك بمعايير غير مخصصة."
        )
    elif module_type == "wheelchair_propulsion" and risk_level in ("red", "amber"):
        top_en = findings[0]["title_en"] if findings else "Elevated shoulder recovery vs personal baseline"
        cue_en = (
            f"Risk indicator for {ipc_class}: {top_en}. "
            f"Combined with a {wow:+.0f}% weekly push-volume shift, focus on keeping your shoulders relaxed and low during push-rim recovery, "
            "shorten your next high-intensity push block by 20%, and consult a qualified sports physiotherapist if shoulder discomfort persists."
        )
        cue_ar = (
            f"مؤشر انتباه لفئة {ipc_class}: تم رصد ارتفاع في الكتف أثناء مرحلة الاسترجاع مقارنة بخط أساسك الشخصي "
            f"مع تغير أسبوعي في أحمال الدفع بنسبة {wow:+.0f}%. حافظ على استرخاء الكتفين للأسفل أثناء استرجاع الذراع، "
            "خفّض حصة الدفع عالية الشدة القادمة بنسبة 20%، واستشر أخصائي علاج طبيعي رياضي إذا استمر أي إجهاد."
        )
    elif module_type == "guide_runner_sync" and risk_level in ("red", "amber"):
        cue_en = (
            f"Guide-runner sync indicator ({ipc_class}): stride phase drifted slightly from your baseline pairing. "
            "Practice 40m rhythmic cadence drills with audible step cues so tether tension stays light and consistent."
        )
        cue_ar = (
            f"مؤشر تزامن مع المرشد لفئة {ipc_class}: لوحظ تباين طفيف في إيقاع الخطوة مقارنة بخط الأساس. "
            "يُنصح بتمارين إيقاع لمسافة 40 متراً مع إشارات صوتية منتظمة للحفاظ على ثبات واسترخاء حبل التوجيه."
        )
    elif risk_level in ("red", "amber"):
        top_en = findings[0]["title_en"] if findings else "Compensatory trunk drift vs personal baseline"
        cue_en = (
            f"Coaching risk indicator ({ipc_class}): {top_en}. "
            "Prioritize core stabilization between intervals and avoid stacking consecutive high-impact track days while load is elevated. "
            "If soreness builds in your intact limb, check in with a qualified physiotherapist."
        )
        cue_ar = (
            f"مؤشر تدريبي لفئة {ipc_class}: لوحظ انحراف تعويضي في استقرار الجذع مقارنة بخط أساسك الشخصي. "
            "ركّز على ثبات الجذع بين التكرارات وتجنب تتابع الأيام عالية الصدمات، واستشر أخصائي علاج طبيعي إذا شعرت بإجهاد."
        )
    else:
        cue_en = (
            f"Solid consistency for {ipc_class}: your kinematics match your personal baseline with a {load_zone.upper()} workload zone. "
            "Maintain your current rhythm and schedule your next 10-second checkpoint clip within 14 days."
        )
        cue_ar = (
            f"أداء متوازن لفئة {ipc_class}: حركتك متوافقة مع خط أساسك الشخصي وحمل التدريب ضمن النطاق الآمن. "
            "حافظ على نفس الإيقاع وسجّل مقطع فحص جديد خلال 14 يوماً."
        )

    conf_en = f"Side-view landmark confidence: {int(detection_confidence * 100)}%. Coaching risk indicator only — not medical diagnosis."
    conf_ar = f"دقة تتبع المفاصل الجانبية: {int(detection_confidence * 100)}%. مؤشر تدريبي فقط وليس تشخيصاً طبياً."

    return {
        "findings": findings,
        "cue_en": cue_en,
        "cue_ar": cue_ar,
        "confidence_note_en": conf_en,
        "confidence_note_ar": conf_ar,
        "ai_source": "template_fallback",
    }


def generate_coaching_feedback(
    keyframe_paths: list[Path],
    metrics: dict,
    baseline_deltas: dict,
    findings: list[dict],
    ipc_class: str,
    module_type: str,
    risk_level: str,
    load_summary: dict,
    detection_confidence: float,
) -> dict:
    """Multimodal Gemini coaching using 3-4 keyframes + structured kinematics + IPC class."""
    client = _get_client()
    if client is None:
        return _template_coaching(module_type, ipc_class, risk_level, findings, load_summary, detection_confidence)

    system_rules = (
        "You are KinetiQ Para, an assistive Para-athletics biomechanics coach. "
        "STRICT RULES: "
        "1) Output a coaching risk indicator only — NEVER medical diagnosis and NEVER assign IPC classification. "
        "2) NEVER compare the Para-athlete to able-bodied norms; reason strictly from their IPC class, assistive equipment "
        "(racing wheelchair, running blade, or guide tether visible in keyframes), and personal self-baseline deltas. "
        "3) Write short, calm, plain-language sentences optimized to be read aloud by screen readers / TTS for visually impaired athletes. "
        "4) Provide natural English (`cue_en`) AND idiomatic Modern Standard Arabic (`cue_ar`). "
        "Return strict JSON with keys: cue_en, cue_ar, confidence_note_en, confidence_note_ar, visual_context_note."
    )

    payload = {
        "ipc_class": ipc_class,
        "module_type": module_type,
        "risk_level": risk_level,
        "detection_confidence": detection_confidence,
        "metrics": metrics,
        "baseline_deltas": baseline_deltas,
        "findings": findings,
        "load_summary": {
            "acwr": load_summary.get("acwr"),
            "wow_change_pct": load_summary.get("wow_change_pct"),
            "load_zone": load_summary.get("load_zone"),
            "limb_load_type": load_summary.get("limb_load_type"),
        },
    }

    parts: list = [
        types.Part.from_text(
            text=(
                f"{system_rules}\n\n"
                f"Analyze the attached track keyframes (confirming assistive equipment context) together with this JSON:\n"
                f"{json.dumps(payload, ensure_ascii=False)}"
            )
        )
    ]
    for kf in keyframe_paths[:4]:
        if kf.exists():
            parts.append(types.Part.from_bytes(data=kf.read_bytes(), mime_type="image/jpeg"))

    try:
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        parsed = json.loads(resp.text or "{}")
        if parsed.get("cue_en") and parsed.get("cue_ar"):
            return {
                "findings": findings,
                "cue_en": str(parsed["cue_en"]).strip(),
                "cue_ar": str(parsed["cue_ar"]).strip(),
                "confidence_note_en": str(
                    parsed.get(
                        "confidence_note_en",
                        f"Vision confidence {int(detection_confidence * 100)}%. Coaching indicator only.",
                    )
                ).strip(),
                "confidence_note_ar": str(
                    parsed.get(
                        "confidence_note_ar",
                        f"دقة الرصد {int(detection_confidence * 100)}%. مؤشر تدريبي فقط.",
                    )
                ).strip(),
                "ai_source": "gemini",
            }
    except Exception:
        pass

    return _template_coaching(module_type, ipc_class, risk_level, findings, load_summary, detection_confidence)


def generate_scout_summary(scout_safe_data: dict) -> tuple[str, str, str]:
    """Synthesize bilingual EN/AR scouting summary strictly from scout-safe passport fields."""
    name = scout_safe_data["full_name"]
    ipc = scout_safe_data["ipc_class"]
    country = scout_safe_data["country"]
    aff = scout_safe_data["affiliation"]
    events = ", ".join(scout_safe_data.get("primary_events", []))
    score = scout_safe_data.get("form_consistency_score", 85.0)
    sessions_30d = scout_safe_data.get("coach_confirmed_sessions_30d", 0)
    verified = [a for a in scout_safe_data.get("achievements", []) if a["verification_tier"] != "self_reported"]
    top_pb = f"{verified[0]['event_name']} ({verified[0]['result_value']})" if verified else events

    fallback_en = (
        f"{name} ({ipc}, {country} — {aff}) competes in {events} with verified best {top_pb}, "
        f"maintaining a {score:.0f}/100 Form Consistency Index across {sessions_30d} coach-confirmed sessions in the past 30 days."
    )
    fallback_ar = (
        f"{scout_safe_data.get('full_name_ar') or name} (فئة {ipc} — {scout_safe_data.get('affiliation_ar') or aff}) "
        f"يتنافس في سباقات {events} بأفضل رقم موثّق {top_pb} ومؤشر ثبات فني {score:.0f}/100 خلال {sessions_30d} حصة تدريبية مؤكدة من المدرب."
    )

    client = _get_client()
    if client is None:
        return fallback_en, fallback_ar, "template_fallback"

    prompt = (
        "Write a concise, factual 2-sentence Paralympic scouting summary in English (`summary_en`) "
        "and Modern Standard Arabic (`summary_ar`) strictly from the verified passport JSON below. "
        "Do NOT mention health, injury, fatigue, or medical details. Return JSON with keys summary_en, summary_ar.\n"
        + json.dumps(scout_safe_data, ensure_ascii=False)
    )
    try:
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3),
        )
        parsed = json.loads(resp.text or "{}")
        if parsed.get("summary_en") and parsed.get("summary_ar"):
            return str(parsed["summary_en"]).strip(), str(parsed["summary_ar"]).strip(), "gemini"
    except Exception:
        pass

    return fallback_en, fallback_ar, "template_fallback"


def translate_scout_nl_query(query: str) -> tuple[dict, str]:
    """Translate natural-language EN/AR scout queries into structured passport filters."""
    q = query.strip()
    filters: dict = {}

    # Try Gemini first if configured
    client = _get_client()
    if client is not None:
        prompt = (
            "Translate this natural-language Paralympic scout query (English or Arabic) into a JSON filter object "
            "with optional keys: ipc_class (e.g. 'T54', 'T64', 'T12', 'T37', 'T40'), event (e.g. '100m', '400m', '800m'), "
            "max_seconds (float), verified_only (bool), country (string). Omit keys not mentioned.\nQuery: " + q
        )
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
            )
            parsed = json.loads(resp.text or "{}")
            if isinstance(parsed, dict) and parsed:
                return {k: v for k, v in parsed.items() if v not in (None, "", [])}, "gemini"
        except Exception:
            pass

    # Deterministic bilingual regex fallback (instant & offline-proof)
    cls_m = re.search(r"\b(T\d{2})\b", q, re.IGNORECASE)
    if cls_m:
        filters["ipc_class"] = cls_m.group(1).upper()
    elif any(w in q.lower() for w in ("wheelchair", "كرسي", "الكراسي")):
        filters["disability_category"] = "wheelchair_racing"
    elif any(w in q.lower() for w in ("blade", "amputee", "prosthe", "طرف صناعي", "بتر")):
        filters["disability_category"] = "prosthetic_standing"
    elif any(w in q.lower() for w in ("visual", "blind", "guide", "بصري", "مكفوف")):
        filters["disability_category"] = "visual_impairment"

    ev_m = re.search(r"\b(100m|200m|400m|800m|1500m)\b", q, re.IGNORECASE)
    if ev_m:
        filters["event"] = ev_m.group(1).lower()

    sec_m = re.search(r"(?:under|below|<|أقل من|تحت)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|ثانية)?", q, re.IGNORECASE)
    if sec_m:
        filters["max_seconds"] = float(sec_m.group(1))

    if any(w in q.lower() for w in ("verified", "official", "موثق", "موثّق", "معتمد")):
        filters["verified_only"] = True

    for country in ("Sri Lanka", "Kuwait", "Qatar", "UAE", "Egypt", "Jordan"):
        if country.lower() in q.lower():
            filters["country"] = country
            break

    return filters, "rule_fallback"
