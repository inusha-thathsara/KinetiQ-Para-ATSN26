"""MediaPipe Tasks PoseLandmarker video pipeline with ffmpeg H.264 overlay export."""

from __future__ import annotations

import math
import shutil
import subprocess
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from app.config import settings

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)

# MediaPipe Pose landmark indices
LM = {
    "nose": 0,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}

UPPER_CONNECTIONS = [
    (7, 11), (8, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
]
LOWER_CONNECTIONS = [
    (23, 25), (25, 27), (24, 26), (26, 28),
]


def ensure_pose_model() -> Path:
    model_path = settings.storage_dir.parent / "models" / "pose_landmarker_lite.task"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if not model_path.exists():
        urllib.request.urlretrieve(MODEL_URL, model_path)
    return model_path


def _find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Check WinGet Links on Windows if PATH wasn't refreshed
    winget_ffmpeg = Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
    if winget_ffmpeg.exists():
        return str(winget_ffmpeg)
    return None


def transcode_h264(raw_mp4: Path, out_mp4: Path) -> Path:
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        if raw_mp4 != out_mp4:
            shutil.copy2(raw_mp4, out_mp4)
        return out_mp4
    cmd = [
        ffmpeg, "-y", "-i", str(raw_mp4),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(out_mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if res.returncode == 0 and out_mp4.exists() and out_mp4.stat().st_size > 0:
        if raw_mp4 != out_mp4 and raw_mp4.exists():
            raw_mp4.unlink(missing_ok=True)
        return out_mp4
    if raw_mp4 != out_mp4:
        shutil.copy2(raw_mp4, out_mp4)
    return out_mp4


def _draw_skeleton(frame: np.ndarray, landmarks: list, upper_only: bool, color=(0, 229, 255)) -> None:
    h, w = frame.shape[:2]
    conns = UPPER_CONNECTIONS if upper_only else UPPER_CONNECTIONS + LOWER_CONNECTIONS
    for a, b in conns:
        la, lb = landmarks[a], landmarks[b]
        if getattr(la, "visibility", 1.0) < 0.35 or getattr(lb, "visibility", 1.0) < 0.35:
            continue
        pa = (int(la.x * w), int(la.y * h))
        pb = (int(lb.x * w), int(lb.y * h))
        cv2.line(frame, pa, pb, color, 3, cv2.LINE_AA)
    idxs = {i for pair in conns for i in pair}
    for i in idxs:
        lm = landmarks[i]
        if getattr(lm, "visibility", 1.0) < 0.35:
            continue
        pt = (int(lm.x * w), int(lm.y * h))
        cv2.circle(frame, pt, 5, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, pt, 5, color, 2, cv2.LINE_AA)


def _extract_lm_dict(landmarks: list) -> dict[str, dict[str, float]]:
    out = {}
    for name, idx in LM.items():
        lm = landmarks[idx]
        out[name] = {
            "x": float(lm.x),
            "y": float(lm.y),
            "z": float(lm.z),
            "v": float(getattr(lm, "visibility", 1.0)),
        }
    return out


def process_video_pose(
    video_path: Path,
    module_type: str,
    clip_prefix: str,
    target_fps: float = 15.0,
    max_seconds: float = 15.0,
) -> dict:
    """Run MediaPipe PoseLandmarker on a side-view clip, render overlay MP4, and save 3-4 keyframes."""
    model_path = ensure_pose_model()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if src_fps <= 1 or src_fps > 240:
        src_fps = 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)

    # Cap resolution to 720p for fast processing
    scale = min(1.0, 960.0 / max(width, 1))
    out_w = max(2, int(width * scale) // 2 * 2)
    out_h = max(2, int(height * scale) // 2 * 2)

    stride = max(1, int(round(src_fps / target_fps)))
    effective_fps = src_fps / stride
    max_src_frames = int(src_fps * max_seconds)

    num_poses = 2 if module_type == "guide_runner_sync" else 1
    upper_only = module_type == "wheelchair_propulsion"

    base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=num_poses,
        min_pose_detection_confidence=0.4,
        min_pose_presence_confidence=0.4,
        min_tracking_confidence=0.4,
    )

    raw_overlay_path = settings.storage_dir / f"{clip_prefix}_overlay_raw.mp4"
    final_overlay_path = settings.storage_dir / f"{clip_prefix}_overlay.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(raw_overlay_path), fourcc, effective_fps, (out_w, out_h))

    frame_records: list[dict] = []
    annotated_frames: list[np.ndarray] = []
    frame_idx = 0
    sampled = 0

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while frame_idx < max_src_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % stride != 0:
                frame_idx += 1
                continue
            if scale < 1.0:
                frame = cv2.resize(frame, (out_w, out_h))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_img)

            t_sec = frame_idx / src_fps
            poses_extracted: list[dict[str, dict[str, float]]] = []
            if result.pose_landmarks:
                colors = [(0, 229, 255), (255, 193, 7)]
                for pi, pose_lms in enumerate(result.pose_landmarks):
                    _draw_skeleton(frame, pose_lms, upper_only=upper_only, color=colors[pi % len(colors)])
                    poses_extracted.append(_extract_lm_dict(pose_lms))

            # HUD banner on overlay video
            cv2.rectangle(frame, (0, 0), (out_w, 34), (15, 23, 42), -1)
            label = f"KinetiQ Para | {module_type.replace('_', ' ').title()} | t={t_sec:.1f}s"
            cv2.putText(frame, label, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

            writer.write(frame)
            if sampled % 3 == 0:
                annotated_frames.append(frame.copy())
            frame_records.append({"t": round(t_sec, 3), "poses": poses_extracted})
            sampled += 1
            frame_idx += 1

    cap.release()
    writer.release()

    final_overlay_path = transcode_h264(raw_overlay_path, final_overlay_path)

    # Save 3-4 evenly spaced keyframes for Gemini Multimodal Vision + UI inspection
    keyframe_filenames: list[str] = []
    if annotated_frames:
        n = len(annotated_frames)
        indices = sorted({int(round(i * (n - 1) / 3)) for i in range(min(4, n))})
        for ki, idx in enumerate(indices):
            kf_name = f"{clip_prefix}_kf_{ki + 1}.jpg"
            kf_path = settings.storage_dir / kf_name
            cv2.imwrite(str(kf_path), annotated_frames[idx], [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            keyframe_filenames.append(kf_name)

    return {
        "fps": round(effective_fps, 2),
        "duration_s": round(sampled / max(effective_fps, 1.0), 2),
        "sampled_frames": sampled,
        "frames": frame_records,
        "overlay_filename": final_overlay_path.name,
        "keyframe_filenames": keyframe_filenames,
    }


def generate_synthetic_demo_clip(
    out_path: Path,
    module_type: str = "wheelchair_propulsion",
    scenario: str = "fatigue_spike",
    duration_s: float = 6.0,
    fps: int = 15,
) -> tuple[Path, list[dict]]:
    """Generate a crisp animated biomechanical visualization clip & matched synthetic landmark series
    for reliable local testing and 1-click live demo fallback when no local MP4 is supplied."""
    w, h = 640, 360
    raw_path = out_path.with_name(out_path.stem + "_raw.mp4")
    writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    total_frames = int(duration_s * fps)
    frames_data: list[dict] = []
    is_fatigue = scenario == "fatigue_spike"

    for i in range(total_frames):
        t = i / fps
        img = np.full((h, w, 3), (18, 28, 46), dtype=np.uint8)
        # Track lane lines
        cv2.line(img, (0, 290), (w, 290), (56, 189, 248), 2)
        cv2.line(img, (0, 315), (w, 315), (30, 64, 110), 1)
        for dash in range(0, w, 60):
            dx = (dash - int(t * 140)) % w
            cv2.line(img, (dx, 302), (dx + 25, 302), (100, 116, 139), 2)

        if module_type == "wheelchair_propulsion":
            # Draw racing wheelchair silhouette
            rear_center = (275, 232)
            front_center = (465, 260)
            cv2.circle(img, rear_center, 58, (148, 163, 184), 3, cv2.LINE_AA)
            cv2.circle(img, rear_center, 36, (203, 213, 225), 2, cv2.LINE_AA)  # push rim
            cv2.circle(img, front_center, 28, (148, 163, 184), 3, cv2.LINE_AA)
            cv2.line(img, rear_center, (345, 250), (226, 232, 240), 4)
            cv2.line(img, (345, 250), front_center, (226, 232, 240), 4)

            freq = 1.65 if is_fatigue else 1.85  # Hz (~99-111 spm)
            phase = 2 * math.pi * freq * t
            shrug_px = 18.0 * (0.5 + 0.5 * math.sin(phase + 0.8)) if is_fatigue else 3.0 * math.sin(phase)

            hip = (288, 222)
            trunk_deg = 44.0 if is_fatigue else 38.0
            torso_len = 96.0
            sh_x = hip[0] + torso_len * math.sin(math.radians(trunk_deg))
            sh_y = hip[1] - torso_len * math.cos(math.radians(trunk_deg)) - shrug_px
            ear_x = sh_x + 14
            ear_y = sh_y - (22.0 if is_fatigue else 34.0)

            # Push-rim wrist trajectory
            wrist_x = rear_center[0] + 34 * math.cos(phase - 0.6)
            wrist_y = rear_center[1] + 34 * math.sin(phase - 0.6)
            elbow_x = (sh_x + wrist_x) * 0.5 - 24
            elbow_y = (sh_y + wrist_y) * 0.5 - (14 if is_fatigue else 4)

            pts = {
                "right_ear": (ear_x, ear_y),
                "right_shoulder": (sh_x, sh_y),
                "right_elbow": (elbow_x, elbow_y),
                "right_wrist": (wrist_x, wrist_y),
                "right_hip": hip,
            }
            # Draw skeleton overlay
            color = (0, 140, 255) if is_fatigue else (52, 211, 153)
            for a, b in [
                ("right_hip", "right_shoulder"),
                ("right_shoulder", "right_ear"),
                ("right_shoulder", "right_elbow"),
                ("right_elbow", "right_wrist"),
            ]:
                p1 = (int(pts[a][0]), int(pts[a][1]))
                p2 = (int(pts[b][0]), int(pts[b][1]))
                cv2.line(img, p1, p2, color, 4, cv2.LINE_AA)
            for p in pts.values():
                cv2.circle(img, (int(p[0]), int(p[1])), 6, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(img, (int(p[0]), int(p[1])), 6, color, 2, cv2.LINE_AA)

            pose_dict = {}
            for name in LM:
                if name in pts:
                    px, py = pts[name]
                    v = 0.94
                elif name.replace("left_", "right_") in pts:
                    px, py = pts[name.replace("left_", "right_")]
                    px -= 8
                    v = 0.72
                else:
                    px, py = hip[0] + 40, hip[1] + 25
                    v = 0.15
                pose_dict[name] = {"x": px / w, "y": py / h, "z": 0.0, "v": v}
            frames_data.append({"t": round(t, 3), "poses": [pose_dict]})
        else:
            # Standing / prosthetic or guide-runner side-view kinematics
            freq = 2.85 if not is_fatigue else 2.55
            phase = 2 * math.pi * freq * t
            bounce = 14 * abs(math.sin(phase)) if is_fatigue else 7 * abs(math.sin(phase))
            hip = (320, 185 - bounce)
            trunk_deg = 21.0 if is_fatigue else 12.0
            sh_x = hip[0] + 82 * math.sin(math.radians(trunk_deg))
            sh_y = hip[1] - 82 * math.cos(math.radians(trunk_deg))
            ear_x, ear_y = sh_x + 4, sh_y - 28
            knee_x = hip[0] + 38 * math.sin(phase)
            knee_y = hip[1] + 52 - 12 * math.cos(phase)
            ankle_x = knee_x + 30 * math.sin(phase - 0.65)
            ankle_y = min(286, knee_y + 52)
            wrist_x = sh_x + 36 * math.sin(phase + math.pi)
            wrist_y = sh_y + 42
            elbow_x = (sh_x + wrist_x) / 2 - 12
            elbow_y = (sh_y + wrist_y) / 2 + 12

            pts = {
                "right_ear": (ear_x, ear_y),
                "right_shoulder": (sh_x, sh_y),
                "right_elbow": (elbow_x, elbow_y),
                "right_wrist": (wrist_x, wrist_y),
                "right_hip": hip,
                "right_knee": (knee_x, knee_y),
                "right_ankle": (ankle_x, ankle_y),
            }
            color = (0, 165, 255) if is_fatigue else (52, 211, 153)
            for a, b in [
                ("right_ear", "right_shoulder"),
                ("right_shoulder", "right_hip"),
                ("right_shoulder", "right_elbow"),
                ("right_elbow", "right_wrist"),
                ("right_hip", "right_knee"),
                ("right_knee", "right_ankle"),
            ]:
                cv2.line(img, (int(pts[a][0]), int(pts[a][1])), (int(pts[b][0]), int(pts[b][1])), color, 4, cv2.LINE_AA)
            for p in pts.values():
                cv2.circle(img, (int(p[0]), int(p[1])), 5, (255, 255, 255), -1, cv2.LINE_AA)

            pose1 = {}
            for name in LM:
                if name in pts:
                    px, py = pts[name]
                    v = 0.93
                elif name.replace("left_", "right_") in pts:
                    px, py = pts[name.replace("left_", "right_")]
                    px -= 10
                    v = 0.25 if module_type == "standing_para_gait" else 0.85
                else:
                    px, py, v = ear_x + 8, ear_y + 2, 0.85
                pose1[name] = {"x": px / w, "y": py / h, "z": 0.0, "v": v}

            poses_list = [pose1]
            if module_type == "guide_runner_sync":
                # Draw second runner (guide) offset horizontally with tether line
                lag = 0.45 if is_fatigue else 0.08
                p2_phase = phase - lag
                g_hip = (210, 185 - 7 * abs(math.sin(p2_phase)))
                g_sh = (g_hip[0] + 15, g_hip[1] - 80)
                g_wr = (g_sh[0] + 34 * math.sin(p2_phase + math.pi), g_sh[1] + 40)
                g_kn = (g_hip[0] + 36 * math.sin(p2_phase), g_hip[1] + 52)
                g_an = (g_kn[0] + 28 * math.sin(p2_phase - 0.65), min(286, g_kn[1] + 52))
                cv2.line(img, (int(g_wr[0]), int(g_wr[1])), (int(wrist_x), int(wrist_y)), (250, 204, 21), 2, cv2.LINE_AA)
                for a, b in [(g_sh, g_hip), (g_sh, g_wr), (g_hip, g_kn), (g_kn, g_an)]:
                    cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (250, 204, 21), 3, cv2.LINE_AA)
                pose2 = {k: dict(val) for k, val in pose1.items()}
                for k in pose2:
                    pose2[k]["x"] = max(0.05, pose2[k]["x"] - 0.17)
                pose2["right_wrist"]["x"] = g_wr[0] / w
                pose2["right_wrist"]["y"] = g_wr[1] / h
                pose2["right_ankle"]["x"] = g_an[0] / w
                pose2["right_ankle"]["y"] = g_an[1] / h
                poses_list.append(pose2)

            frames_data.append({"t": round(t, 3), "poses": poses_list})

        # HUD header
        cv2.rectangle(img, (0, 0), (w, 34), (15, 23, 42), -1)
        banner = f"KinetiQ Para Demo | {module_type.replace('_', ' ').title()} | {scenario.replace('_', ' ').title()}"
        cv2.putText(img, banner, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        writer.write(img)

    writer.release()
    final_path = transcode_h264(raw_path, out_path)
    return final_path, frames_data
