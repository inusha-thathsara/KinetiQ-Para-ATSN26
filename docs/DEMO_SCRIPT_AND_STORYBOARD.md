# KinetiQ Para — ATSN'26 Phase II Video Storyboard (≤60s) & Phase III Live Demo Script

## 1. Strict 60-Second Phase II Video Storyboard (Target: 55s with 5s safety buffer)

> **Mandatory Accessibility Rules (ATSN'26 Guidelines):**
> - Exact hard limit: **≤ 60 seconds** (do NOT exceed 1:00).
> - **Burned-in closed captions (SRT)** required for deaf/hard-of-hearing judges.
> - **Spoken audio descriptions** of visual actions required for blind/low-vision judges.

| Time | Segment | Visuals on Screen | Narration / Captions |
|---|---|---|---|
| **0:00–0:09** | **The Hook & Barrier** | Landing screen + split contrast showing able-bodied pose AI failing vs. wheelchair racer & blade runner. | "Grassroots Para-track athletes train without biomechanists. Able-bodied sports AI breaks on racing wheelchairs and running blades, missing shoulder injuries that threaten everyday independence." |
| **0:09–0:23** | **Why Multimodal GenAI** | Click **Tariq Al-Mansoor (IPC T54)** → click **1-Click Live Demo (Fatigue Spike)** → MediaPipe upper-body overlay plays + 3 Gemini keyframes appear. | "Meet KinetiQ Para. From a 12-second smartphone clip, MediaPipe tracks upper-body propulsion while Gemini 2.5 Vision verifies wheelchair context and compares against each athlete's own baseline—never able-bodied norms." |
| **0:23–0:44** | **Live Demo: Shoulder Flag, Arabic Voice & 2-Layer Privacy** | 1) Show **+11.0° shoulder elevation** Red flag + **ACWR +35% spike**. 2) Click **العربية (RTL)** + **High Contrast** + **استمع للتوجيه الصوتي** (hear Arabic TTS). 3) Switch to **Coach** → 1-click **Approve Coach-Verified** on `50.84s` 400m PB. 4) Switch to **Scout** → run AI search `verified T54 400m under 52s` → open Passport (injury alert completely hidden) & click **PDF**. | "Here, KinetiQ Para flags an 11-degree shoulder rise after a heavy push week. One tap switches to WCAG AAA high contrast and Arabic RTL with spoken coaching for visually impaired T11 to T13 runners. Coaches verify PBs in one click, and our two-layer privacy passport hides private injury alerts from external scouts." |
| **0:44–0:55** | **Impact & Readiness** | Show 5 seeded IPC classes (T54, T64, T12, T37, T40) + PDF passport + ATSN'26 / Mada roadmap. | "Working end-to-end today across wheelchair racing, prosthetic gait, and guide-runner sync—protecting mobility, empowering autonomy in English and Arabic, and ready for Mada Innovation Award scale." |

---

## 2. Phase III Live Hybrid Jury Demo Script (5 Minutes, Dec 13–14)

1. **Pre-flight Check (10 min before pitch):**
   - Start API: `cd apps/api && uv run uvicorn app.main:app --port 8000`
   - Start Web: `cd apps/web && npm run dev`
   - Confirm `http://localhost:3000` loads all 6 seeded demo roles cleanly. Keep the pre-recorded 60s video open as backup.
2. **Step 1 — Athlete Role (Tariq Al-Mansoor, IPC T54):**
   - Show the WCAG AAA Accessibility Bar (High Contrast, `A+` scaling, Arabic RTL toggle, Voice Guide).
   - Run **1-Click Live Demo (Fatigue Spike)** or upload a clip from `data/clips/` → show H.264 overlay, 3 keyframes, `+11.0° vs personal baseline`, and play the spoken English + Arabic coaching cues.
3. **Step 2 — Coach Role (Dr. Samira Al-Kuwari):**
   - Show the Readiness Dashboard sorted by urgency (Tariq Red, Kavindu outdated >14d clip decay).
   - Log a 1-click squad workout (zero daily athlete check-ins) and watch ACWR update live.
   - Click **Approve (Coach-Verified)** on Tariq's `50.84s` 400m PB.
4. **Step 3 — NPC Scout Role (Rohan Jayawardena):**
   - Point out the **2-Layer Privacy Shield** (and mention the automated pytest leak guard!).
   - Run natural-language bilingual query `"verified T54 400m under 52s"` and `"متسابقي كراسي متحركة T54 موثق"`.
   - Click **Accessible PDF** to download the verified Para-Athlete Passport live.
