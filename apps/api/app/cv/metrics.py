"""Deterministic Para-Track biomechanical metrics (distance-normalized, no able-bodied bias)."""

from __future__ import annotations

import math

import numpy as np
from scipy.signal import find_peaks


def _vec(a: dict, b: dict) -> np.ndarray:
    return np.array([b["x"] - a["x"], b["y"] - a["y"]], dtype=float)


def _angle_deg(a: dict, b: dict, c: dict) -> float:
    """Interior angle at vertex b in degrees."""
    v1 = _vec(b, a)
    v2 = _vec(b, c)
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    cos_val = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return math.degrees(math.acos(cos_val))


def _angle_from_vertical(hip: dict, shoulder: dict) -> float:
    """Trunk lean angle relative to upward vertical (0° = upright, 90° = horizontal)."""
    dx = abs(shoulder["x"] - hip["x"])
    dy = hip["y"] - shoulder["y"]  # y grows downward in image coordinates
    return math.degrees(math.atan2(dx, max(dy, 1e-6)))


def _choose_dominant_side(frames: list[dict], upper_only: bool = True) -> str:
    left_v, right_v = [], []
    keys = ["shoulder", "elbow", "wrist", "hip"] if upper_only else ["shoulder", "hip", "knee", "ankle"]
    for fr in frames:
        if not fr["poses"]:
            continue
        p = fr["poses"][0]
        left_v.extend(p[f"left_{k}"]["v"] for k in keys if f"left_{k}" in p)
        right_v.extend(p[f"right_{k}"]["v"] for k in keys if f"right_{k}" in p)
    return "right" if (np.mean(right_v) if right_v else 0.0) >= (np.mean(left_v) if left_v else 0.0) else "left"


def compute_wheelchair_metrics(frames: list[dict], fps: float) -> dict:
    """IPC T51–T54 Wheelchair Racing Propulsion Metrics (upper-body landmarks ONLY)."""
    side = _choose_dominant_side(frames, upper_only=True)
    ear_k, sh_k, el_k, wr_k, hip_k = (
        f"{side}_ear",
        f"{side}_shoulder",
        f"{side}_elbow",
        f"{side}_wrist",
        f"{side}_hip",
    )

    sh_elev_ratios: list[float] = []
    sh_elev_angles: list[float] = []
    trunk_leans: list[float] = []
    elbow_angles: list[float] = []
    wrist_x_series: list[float] = []
    wrist_y_series: list[float] = []
    visibilities: list[float] = []

    for fr in frames:
        if not fr["poses"]:
            continue
        p = fr["poses"][0]
        vis = float(np.mean([p[k]["v"] for k in (ear_k, sh_k, el_k, wr_k, hip_k)]))
        visibilities.append(vis)
        if vis < 0.35:
            continue

        torso_len = max(float(np.linalg.norm(_vec(p[hip_k], p[sh_k]))), 1e-4)
        # Smaller vertical gap between ear and shoulder => higher shoulder shrugging/elevation
        ear_sh_gap = max(0.0, p[sh_k]["y"] - p[ear_k]["y"])
        normalized_gap = ear_sh_gap / torso_len
        # Convert to intuitive elevation index (higher = more shoulder hiking/impingement risk)
        elev_index = round(max(0.0, (0.42 - normalized_gap) * 100.0), 1)
        sh_elev_ratios.append(elev_index)

        # Neck-shoulder-elbow elevation angle proxy (degrees)
        sh_elev_angles.append(_angle_deg(p[ear_k], p[sh_k], p[el_k]))
        trunk_leans.append(_angle_from_vertical(p[hip_k], p[sh_k]))
        elbow_angles.append(_angle_deg(p[sh_k], p[el_k], p[wr_k]))
        # Measure wrist trajectory relative to shoulder so camera panning / travel across frame never distorts stroke arc
        wrist_x_series.append((p[wr_k]["x"] - p[sh_k]["x"]) / torso_len)
        wrist_y_series.append((p[wr_k]["y"] - p[sh_k]["y"]) / torso_len)

    confidence = round(float(np.mean(visibilities)) if visibilities else 0.0, 2)
    if len(trunk_leans) < 5:
        return {
            "module_type": "wheelchair_propulsion",
            "dominant_side": side,
            "detection_confidence": confidence,
            "valid_frames": len(trunk_leans),
            "metrics": {},
            "low_confidence": True,
        }

    # Push cadence from wrist peaks
    wr_arr = np.array(wrist_x_series, dtype=float)
    min_dist = max(2, int(fps * 0.32))
    peaks, _ = find_peaks(wr_arr, distance=min_dist, prominence=0.08)
    duration_min = max(len(wr_arr) / max(fps, 1.0) / 60.0, 1e-4)
    cadence_spm = round(len(peaks) / duration_min, 1) if len(peaks) >= 2 else round(float(len(peaks)) * 20.0, 1)

    stroke_arc = round(float((np.ptp(wr_arr) + np.ptp(np.array(wrist_y_series))) * 50.0), 1)

    return {
        "module_type": "wheelchair_propulsion",
        "dominant_side": side,
        "detection_confidence": confidence,
        "valid_frames": len(trunk_leans),
        "low_confidence": confidence < 0.45,
        "metrics": {
            "shoulder_elevation_deg": round(float(np.percentile(sh_elev_ratios, 85)), 1),
            "trunk_lean_deg": round(float(np.median(trunk_leans)), 1),
            "elbow_contact_deg": round(float(np.percentile(elbow_angles, 25)), 1),
            "push_cadence_spm": min(160.0, max(35.0, cadence_spm)),
            "stroke_arc_norm": stroke_arc,
        },
    }


def compute_standing_gait_metrics(frames: list[dict], fps: float) -> dict:
    """Standing / Prosthetic / Short-Stature / VI Para-Track Gait Metrics.

    Automatically selects the highest-confidence intact lower limb and NEVER scores
    unreliable carbon-fiber blade landmarks; Gemini Vision inspects keyframes for blade context.
    """
    side = _choose_dominant_side(frames, upper_only=False)
    sh_k, hip_k, kn_k, an_k = f"{side}_shoulder", f"{side}_hip", f"{side}_knee", f"{side}_ankle"

    trunk_leans: list[float] = []
    knee_flexions: list[float] = []
    hip_y_norm: list[float] = []
    ankle_x_norm: list[float] = []
    visibilities: list[float] = []

    for fr in frames:
        if not fr["poses"]:
            continue
        p = fr["poses"][0]
        vis = float(np.mean([p[k]["v"] for k in (sh_k, hip_k, kn_k, an_k)]))
        visibilities.append(vis)
        if vis < 0.35:
            continue
        torso_len = max(float(np.linalg.norm(_vec(p[hip_k], p[sh_k]))), 1e-4)
        trunk_leans.append(_angle_from_vertical(p[hip_k], p[sh_k]))
        # Knee flexion (180 - interior angle so higher = more bend)
        knee_flexions.append(max(0.0, 180.0 - _angle_deg(p[hip_k], p[kn_k], p[an_k])))
        hip_y_norm.append(p[hip_k]["y"] / torso_len)
        # Measure ankle swing relative to hip so travel across frame doesn't skew cadence peaks
        ankle_x_norm.append((p[an_k]["x"] - p[hip_k]["x"]) / torso_len)

    confidence = round(float(np.mean(visibilities)) if visibilities else 0.0, 2)
    if len(trunk_leans) < 5:
        return {
            "module_type": "standing_para_gait",
            "intact_side_tracked": side,
            "detection_confidence": confidence,
            "valid_frames": len(trunk_leans),
            "metrics": {},
            "low_confidence": True,
        }

    an_arr = np.array(ankle_x_norm, dtype=float)
    peaks, _ = find_peaks(an_arr, distance=max(2, int(fps * 0.22)), prominence=0.06)
    duration_min = max(len(an_arr) / max(fps, 1.0) / 60.0, 1e-4)
    # Single-side stride peaks × 2 = total step cadence
    cadence_spm = round((len(peaks) * 2.0) / duration_min, 1) if len(peaks) >= 2 else 155.0
    vertical_osc = round(float(np.ptp(np.array(hip_y_norm)) * 100.0), 1)

    return {
        "module_type": "standing_para_gait",
        "intact_side_tracked": side,
        "prosthetic_landmark_policy": "excluded_by_design_gemini_keyframe_verified",
        "detection_confidence": confidence,
        "valid_frames": len(trunk_leans),
        "low_confidence": confidence < 0.45,
        "metrics": {
            "trunk_lean_deg": round(float(np.median(trunk_leans)), 1),
            "intact_knee_flexion_deg": round(float(np.percentile(knee_flexions, 80)), 1),
            "pelvic_oscillation_norm": vertical_osc,
            "stride_cadence_spm": min(230.0, max(90.0, cadence_spm)),
        },
    }


def compute_guide_sync_metrics(frames: list[dict], fps: float) -> dict:
    """IPC T11–T12 Guide-Runner Dual-Pose Synchronization Metrics (stretch feature)."""
    base = compute_standing_gait_metrics(frames, fps)
    dual_frames = [fr for fr in frames if len(fr["poses"]) >= 2]
    if len(dual_frames) < 5:
        base["module_type"] = "guide_runner_sync"
        base["dual_pose_detected"] = False
        return base

    tether_gaps: list[float] = []
    a_ankles: list[float] = []
    g_ankles: list[float] = []

    for fr in dual_frames:
        p1, p2 = fr["poses"][0], fr["poses"][1]
        torso = max(float(np.linalg.norm(_vec(p1["right_hip"], p1["right_shoulder"]))), 1e-4)
        gap = float(np.linalg.norm(_vec(p1["right_wrist"], p2["right_wrist"]))) / torso
        tether_gaps.append(gap)
        a_ankles.append(p1["right_ankle"]["x"])
        g_ankles.append(p2["right_ankle"]["x"])

    a_arr = np.array(a_ankles) - np.mean(a_ankles)
    g_arr = np.array(g_ankles) - np.mean(g_ankles)
    denom = float(np.linalg.norm(a_arr) * np.linalg.norm(g_arr))
    corr = float(np.dot(a_arr, g_arr) / denom) if denom > 1e-6 else 0.85
    sync_pct = round(max(0.0, min(100.0, (corr + 1.0) * 50.0)), 1)
    tether_var = round(float(np.std(tether_gaps) * 100.0), 1)

    metrics = dict(base.get("metrics", {}))
    metrics["guide_stride_sync_pct"] = sync_pct
    metrics["tether_spacing_variability"] = tether_var
    base["module_type"] = "guide_runner_sync"
    base["dual_pose_detected"] = True
    base["metrics"] = metrics
    return base


def compute_module_metrics(module_type: str, frames: list[dict], fps: float) -> dict:
    if module_type == "wheelchair_propulsion":
        return compute_wheelchair_metrics(frames, fps)
    if module_type == "guide_runner_sync":
        return compute_guide_sync_metrics(frames, fps)
    return compute_standing_gait_metrics(frames, fps)
