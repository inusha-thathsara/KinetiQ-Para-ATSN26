# KinetiQ Para

**Assistive GenAI Biomechanics, Load Safety & Verified Passport for Para-Track Athletes**

## Overview

KinetiQ Para is a WCAG AAA-accessible, bilingual (**English & Arabic RTL**) assistive AI platform designed for Para-track athletes and coaches—including:
- **Wheelchair Racers (`IPC T51–T54`)** — Upper-body push-rim propulsion analysis & shoulder/wrist overuse prevention.
- **Standing & Prosthetic Para-Runners (`T35–T47`, `T61–T64`)** — Impairment-aware self-baseline gait tracking without able-bodied bias.
- **Visually Impaired Runners (`T11–T13`)** — Voice-first English & Arabic audio coaching and guide-runner synchronization.

## Core Pillars

1. **Adaptive Form Check (MediaPipe + Gemini 2.5 Multimodal Vision):** 10–15s side-view smartphone clip analysis with equipment-context verification and plain-language spoken coaching cues.
2. **Para Session Load Guard:** Zero daily athlete check-ins; coach-logged squad sessions track upper-limb and lower-limb Acute-to-Chronic Workload Ratios (ACWR).
3. **Accessible Coach & Athlete Readiness Dashboard:** WCAG AAA high-contrast mode, scalable fonts, keyboard navigation, Arabic RTL layout, and built-in TTS Voice Guide.
4. **Verified Para-Athlete Passport:** IPC-class-indexed, shareable portfolio with 3-tier verification and a strict 2-layer privacy split (keeping injury/health flags private).

## Tech Stack

- **AI & Vision:** Google Gemini 2.5 Flash/Pro Multimodal API, MediaPipe Pose, OpenCV, NumPy
- **Backend:** Python FastAPI, PostgreSQL / Firebase, Cloud Object Storage
- **Frontend:** Next.js (React), Tailwind CSS (WCAG AAA & Arabic RTL), Web Speech API / Multilingual TTS
