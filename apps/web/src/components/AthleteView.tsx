"use client";

import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  Award,
  Camera,
  CheckCircle2,
  Download,
  Lock,
  PlayCircle,
  Shield,
  Sparkles,
  Upload,
  Volume2,
} from "lucide-react";
import {
  apiFetch,
  downloadPassportPdf,
  mediaUrl,
  PrivateClip,
  PrivateHealthView,
} from "@/lib/api";
import {
  ADJUSTMENT_LABELS,
  CATEGORY_LABELS,
  DICT,
  Lang,
  RISK_LABELS,
  TIER_LABELS,
  trMap,
  WITNESS_LABELS,
} from "@/lib/i18n";

interface AthleteViewProps {
  data: PrivateHealthView;
  token: string;
  lang: Lang;
  onRefresh: () => Promise<void>;
  onSpeak: (text: string, speakLang?: Lang) => void;
  onAnnounce: (msg: string) => void;
}

function zoneClasses(zone: string) {
  if (zone === "red") return "bg-rose-100 text-rose-900 border-rose-400";
  if (zone === "amber") return "bg-amber-100 text-amber-900 border-amber-400";
  if (zone === "baseline_building") return "bg-sky-100 text-sky-900 border-sky-400";
  return "bg-emerald-100 text-emerald-900 border-emerald-400";
}

export function AthleteView({
  data,
  token,
  lang,
  onRefresh,
  onSpeak,
  onAnnounce,
}: AthleteViewProps) {
  const t = DICT[lang];
  const defaultModule =
    data.disability_category === "wheelchair_racing"
      ? "wheelchair_propulsion"
      : data.disability_category === "visual_impairment"
        ? "guide_runner_sync"
        : "standing_para_gait";

  const [moduleType, setModuleType] = useState<string>(defaultModule);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [activeClip, setActiveClip] = useState<PrivateClip | null>(data.latest_clip);

  // New PB form
  const [showPbForm, setShowPbForm] = useState(false);
  const [pbEvent, setPbEvent] = useState(data.primary_events[0] || "400m");
  const [pbResult, setPbResult] = useState("50.65s");
  const [pbSeconds, setPbSeconds] = useState("50.65");
  const [pbMeet, setPbMeet] = useState("Regional Para Track Trials 2026");
  const [pbProof, setPbProof] = useState("official_timing_sheet.pdf");

  const clip = activeClip || data.latest_clip;

  async function pollClip(clipId: number) {
    for (let i = 0; i < 40; i++) {
      const updated = await apiFetch<PrivateClip>(`/api/clips/${clipId}`, {}, token);
      setActiveClip(updated);
      if (updated.status === "completed" || updated.status === "failed") {
        await onRefresh();
        onAnnounce(
          updated.status === "completed"
            ? lang === "ar"
              ? "اكتمل تحليل الفيديو بنجاح"
              : "Video analysis completed."
            : `Analysis failed: ${updated.error_message}`
        );
        return;
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;
    setBusy(true);
    onAnnounce(lang === "ar" ? "جاري رفع وتحليل المقطع..." : "Uploading and running MediaPipe + Gemini analysis...");
    try {
      const fd = new FormData();
      fd.append("file", selectedFile);
      fd.append("module_type", moduleType);
      const created = await apiFetch<PrivateClip>("/api/clips/upload", { method: "POST", body: fd }, token);
      setActiveClip(created);
      await pollClip(created.id);
    } catch (err) {
      onAnnounce(`Upload error: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleDemoAnalyze(scenario: "fatigue_spike" | "optimal_baseline") {
    setBusy(true);
    onAnnounce(
      lang === "ar"
        ? "جاري تشغيل فحص الحركة التجريبي..."
        : "Running live side-view Para-Track pose & GenAI coaching analysis..."
    );
    try {
      const res = await apiFetch<PrivateClip>(
        "/api/clips/analyze-demo",
        {
          method: "POST",
          body: JSON.stringify({
            athlete_id: data.athlete_id,
            module_type: moduleType,
            scenario,
          }),
        },
        token
      );
      setActiveClip(res);
      await onRefresh();
      onAnnounce(lang === "ar" ? "تم تحديث التحليل التكيّفي." : "Adaptive Form Check updated.");
    } catch (err) {
      onAnnounce(`Error: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleTogglePrivacy() {
    const next = !data.passport_public;
    await apiFetch(
      `/api/athletes/${data.athlete_id}/privacy`,
      { method: "PATCH", body: JSON.stringify({ passport_public: next }) },
      token
    );
    await onRefresh();
    onAnnounce(next ? "Scout Passport set to Public (health data remains private)." : "Passport set to Private.");
  }

  async function handleLogPb(e: React.FormEvent) {
    e.preventDefault();
    await apiFetch(
      "/api/achievements",
      {
        method: "POST",
        body: JSON.stringify({
          event_name: pbEvent,
          ipc_class: data.ipc_class,
          result_value: pbResult,
          result_seconds: parseFloat(pbSeconds) || 50.0,
          competition_name: pbMeet,
          achieved_date: new Date().toISOString().slice(0, 10),
          proof_reference: pbProof,
          is_pb: true,
        }),
      },
      token
    );
    setShowPbForm(false);
    await onRefresh();
    onAnnounce("New PB logged as Self-Reported (awaiting Coach verification).");
  }

  const maxWeekly = Math.max(...data.load_summary.weekly_series, 1);

  return (
    <div className="space-y-6">
      {/* Athlete Header Card */}
      <section className="k-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-[#1b365d] px-3 py-0.5 text-xs font-bold text-white">
                IPC {data.ipc_class}
              </span>
              <span className="rounded-full bg-slate-200 px-3 py-0.5 text-xs font-semibold text-slate-800">
                {trMap(CATEGORY_LABELS, data.disability_category, lang)}
              </span>
              {data.is_demo_data && (
                <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-900">
                  {t.demoProfile}
                </span>
              )}
            </div>
            <h1 className="mt-2 text-2xl font-extrabold">
              {lang === "ar" ? data.full_name_ar : data.full_name}
            </h1>
            <p className="text-sm text-slate-600">
              {data.primary_events.join(" · ")} —{" "}
              {lang === "ar" ? data.load_summary.combined_reason_ar : data.load_summary.combined_reason_en}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className={`rounded-xl border px-4 py-2 text-center ${zoneClasses(data.load_summary.overall_zone)}`}>
              <div className="text-xs font-semibold uppercase">{t.readiness}</div>
              <div className="text-2xl font-black">{data.load_summary.readiness_score}/100</div>
            </div>
            <button
              type="button"
              onClick={() => downloadPassportPdf(data.athlete_id, token)}
              className="k-btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              {t.viewMyPassportPdf}
            </button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Adaptive Form Check Studio */}
        <section className="k-card space-y-5 p-5 lg:col-span-8" aria-labelledby="form-check-h">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="form-check-h" className="flex items-center gap-2 text-lg font-bold">
              <Sparkles className="h-5 w-5 text-sky-700" aria-hidden="true" />
              {t.formCheckTitle}
            </h2>
          </div>

          {/* Camera setup voice guide */}
          <div className="k-muted flex flex-wrap items-center justify-between gap-3 p-3.5">
            <div className="flex items-start gap-2.5 text-sm">
              <Camera className="mt-0.5 h-5 w-5 shrink-0 text-sky-700" aria-hidden="true" />
              <div>
                <p className="font-semibold">{t.cameraGuideTitle}</p>
                <p className="text-xs opacity-90">{t.cameraGuideText}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onSpeak(t.cameraGuideText, lang)}
              className="inline-flex items-center gap-1.5 rounded-md border border-sky-600 px-3 py-1.5 text-xs font-semibold text-sky-800 hover:bg-sky-50"
            >
              <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
              {t.speakCameraGuide}
            </button>
          </div>

          {/* Upload & 1-Click Live Demo Controls */}
          <form onSubmit={handleUpload} className="space-y-3 rounded-lg border border-slate-200 p-4">
            <label className="block text-sm font-semibold">
              {t.moduleLabel}
              <select
                value={moduleType}
                onChange={(e) => setModuleType(e.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              >
                <option value="wheelchair_propulsion">{t.modWheelchair}</option>
                <option value="standing_para_gait">{t.modStanding}</option>
                <option value="guide_runner_sync">{t.modGuide}</option>
              </select>
            </label>

            <div className="flex flex-wrap items-end gap-3">
              <label className="flex-1 text-sm font-semibold">
                {t.uploadLabel}
                <input
                  type="file"
                  accept="video/mp4,video/quicktime,video/*"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-1.5 text-xs text-slate-900"
                />
              </label>
              <button
                type="submit"
                disabled={!selectedFile || busy}
                className="k-btn-primary inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold disabled:opacity-50"
              >
                <Upload className="h-4 w-4" aria-hidden="true" />
                {t.analyzeUpload}
              </button>
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                disabled={busy}
                onClick={() => handleDemoAnalyze("fatigue_spike")}
                className="inline-flex items-center gap-1.5 rounded-md border border-amber-500 bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-950 hover:bg-amber-100 disabled:opacity-50"
              >
                <PlayCircle className="h-4 w-4" aria-hidden="true" />
                {t.runDemoFatigue}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => handleDemoAnalyze("optimal_baseline")}
                className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-950 hover:bg-emerald-100 disabled:opacity-50"
              >
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                {t.runDemoBaseline}
              </button>
            </div>
          </form>

          {/* Latest Clip Analysis Output */}
          {clip && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {/* Annotated Overlay Video */}
                <div className="space-y-2">
                  {clip.overlay_url && (
                    <video
                      key={clip.overlay_url}
                      src={mediaUrl(clip.overlay_url)}
                      controls
                      playsInline
                      className="w-full rounded-lg border border-slate-300 bg-slate-950"
                      aria-label="Annotated pose overlay video"
                    />
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="font-semibold">
                      {t.formScore}: <span className="text-sky-700">{clip.form_score}/100</span>
                    </span>
                    <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-800">
                      {trMap(WITNESS_LABELS, clip.witness_badge, lang)}
                    </span>
                    <span className={`rounded border px-2 py-0.5 font-bold uppercase ${zoneClasses(clip.risk_level)}`}>
                      {trMap(RISK_LABELS, clip.risk_level, lang)}
                    </span>
                  </div>
                </div>

                {/* Bilingual GenAI Coaching Cue Box */}
                <div className="flex flex-col justify-between rounded-lg border-s-4 border-teal-600 bg-teal-50/70 p-4 text-slate-900">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold uppercase tracking-wide text-teal-900">
                        {t.genaiCoaching} ({clip.ai_source})
                      </span>
                      <span className="text-xs font-semibold text-slate-700">
                        {t.confidence}: {Math.round(clip.detection_confidence * 100)}%
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-relaxed">
                      {lang === "ar" ? clip.cue_ar : clip.cue_en}
                    </p>
                    <p className="text-xs text-slate-700">
                      {lang === "ar" ? clip.confidence_note_ar : clip.confidence_note_en}
                    </p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => onSpeak(lang === "ar" ? clip.cue_ar : clip.cue_en, lang)}
                      className="inline-flex items-center gap-1.5 rounded-md bg-teal-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-600"
                    >
                      <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
                      {t.listenCue}
                    </button>
                    <button
                      type="button"
                      onClick={() => onSpeak(lang === "ar" ? clip.cue_en : clip.cue_ar, lang === "ar" ? "en" : "ar")}
                      className="inline-flex items-center gap-1.5 rounded-md border border-teal-700 bg-white px-3 py-1.5 text-xs font-semibold text-teal-900 hover:bg-teal-50"
                    >
                      <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
                      {lang === "ar" ? "Listen (EN)" : "استمع بالعربية"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Multimodal Keyframes */}
              {clip.keyframe_urls.length > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-600">
                    {t.keyframesTitle}
                  </h3>
                  <div className="grid grid-cols-3 gap-2">
                    {clip.keyframe_urls.slice(0, 3).map((kf, i) => (
                      <img
                        key={kf}
                        src={mediaUrl(kf)}
                        alt={`Multimodal biomechanical keyframe ${i + 1}`}
                        className="h-24 w-full rounded-md border border-slate-300 object-cover"
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Self-Baseline Drift Cards */}
              <div>
                <h3 className="mb-2 text-sm font-bold">{t.selfBaselineTitle}</h3>
                {clip.risk_level === "baseline_building" ? (
                  <p className="rounded-md border border-sky-300 bg-sky-50 p-3 text-xs font-medium text-sky-950">
                    {t.baselineBuildingNote}
                  </p>
                ) : (
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    {Object.entries(clip.baseline_deltas_json).map(([k, d]) => (
                      <div key={k} className={`rounded-lg border p-3 ${zoneClasses(d.status)}`}>
                        <div className="text-xs font-bold">{lang === "ar" ? d.label_ar : d.label_en}</div>
                        <div className="mt-1 text-lg font-black">
                          {d.current}
                          {d.unit}
                        </div>
                        <div className="text-xs">
                          {d.delta >= 0 ? "+" : ""}
                          {d.delta}
                          {d.unit} {t.vsBaseline} (z={d.z_score})
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Responsible-Use Disclaimer */}
          <div className="rounded-md border-s-4 border-rose-600 bg-rose-50 p-3 text-xs text-rose-950">
            <strong>{t.disclaimerLabel}: </strong>
            {lang === "ar" ? data.disclaimer_ar : data.disclaimer_en}
          </div>
        </section>

        {/* Right Column: Session Load Guard + Achievements + Privacy */}
        <div className="space-y-6 lg:col-span-4">
          <section className="k-card space-y-3 p-5" aria-labelledby="load-guard-h">
            <h2 id="load-guard-h" className="flex items-center gap-2 text-base font-bold">
              <Activity className="h-5 w-5 text-sky-700" aria-hidden="true" />
              {t.loadGuardTitle}
            </h2>
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="k-muted p-2.5">
                <div className="text-xs opacity-80">{t.acwrLabel}</div>
                <div className="text-xl font-black">{data.load_summary.acwr}</div>
              </div>
              <div className="k-muted p-2.5">
                <div className="text-xs opacity-80">{t.wowLabel}</div>
                <div className="text-xl font-black">
                  {data.load_summary.wow_change_pct > 0 ? "+" : ""}
                  {data.load_summary.wow_change_pct}%
                </div>
              </div>
            </div>

            {/* 4-week bar chart */}
            <div className="space-y-1">
              <div className="text-xs font-semibold">
                {t.workloadTrend} ({data.limb_load_type === "upper_limb" ? t.upperLimbLabel : t.lowerLimbLabel})
              </div>
              <div className="flex h-24 items-end gap-2 rounded-md border border-slate-200 p-2">
                {data.load_summary.weekly_series.map((val, idx) => (
                  <div key={idx} className="flex flex-1 flex-col items-center gap-1">
                    <div
                      className={`w-full rounded-t ${idx === 3 && data.load_summary.load_zone === "red" ? "bg-rose-600" : "bg-sky-600"}`}
                      style={{ height: `${Math.max(10, Math.round((val / maxWeekly) * 64))}px` }}
                      title={`${idx === 3 ? t.weekNow : `${t.weekPrefix}${3 - idx}`}: ${val}`}
                    />
                    <span className="text-[10px] font-semibold">
                      {idx === 3 ? t.weekNow : `${t.weekPrefix}${3 - idx}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-800">
              <span className="font-semibold">{t.freshnessLabel}:</span>
              <span className={data.load_summary.clip_freshness.status === "outdated" ? "font-bold text-amber-800" : "font-bold text-emerald-800"}>
                {lang === "ar" ? data.load_summary.clip_freshness.label_ar : data.load_summary.clip_freshness.label_en}
              </span>
            </div>

            {data.coach_notes.length > 0 && (
              <div className="space-y-1.5 border-t border-slate-200 pt-2">
                <div className="text-xs font-bold uppercase text-slate-600">{t.coachNotesTitle}</div>
                {data.coach_notes.slice(0, 2).map((n) => (
                  <div key={n.id} className="rounded border border-sky-200 bg-sky-50 p-2 text-xs text-slate-900">
                    <span className="font-bold uppercase text-sky-800">
                      [{trMap(ADJUSTMENT_LABELS, n.load_adjustment, lang)}]
                    </span>{" "}
                    {n.note_text}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Achievements & 3-Tier Verification */}
          <section className="k-card space-y-3 p-5" aria-labelledby="ach-h">
            <div className="flex items-center justify-between gap-2">
              <h2 id="ach-h" className="flex items-center gap-2 text-base font-bold">
                <Award className="h-5 w-5 text-amber-600" aria-hidden="true" />
                {t.achievementsTitle}
              </h2>
              <button
                type="button"
                onClick={() => setShowPbForm((v) => !v)}
                className="rounded-md border border-sky-600 px-2.5 py-1 text-xs font-semibold text-sky-800 hover:bg-sky-50"
              >
                + {t.logPbBtn}
              </button>
            </div>

            {showPbForm && (
              <form onSubmit={handleLogPb} className="space-y-2 rounded-md border border-slate-200 p-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <input value={pbEvent} onChange={(e) => setPbEvent(e.target.value)} placeholder={t.pbEventPh} className="rounded border p-1.5 text-slate-900" required />
                  <input value={pbResult} onChange={(e) => setPbResult(e.target.value)} placeholder={t.pbResultPh} className="rounded border p-1.5 text-slate-900" required />
                </div>
                <input value={pbSeconds} onChange={(e) => setPbSeconds(e.target.value)} placeholder={t.pbSecondsPh} className="w-full rounded border p-1.5 text-slate-900" required />
                <input value={pbMeet} onChange={(e) => setPbMeet(e.target.value)} placeholder={t.pbMeetPh} className="w-full rounded border p-1.5 text-slate-900" required />
                <input value={pbProof} onChange={(e) => setPbProof(e.target.value)} placeholder={t.pbProofPh} className="w-full rounded border p-1.5 text-slate-900" />
                <button type="submit" className="k-btn-primary w-full rounded py-1.5 font-bold">
                  {t.pbSubmitBtn}
                </button>
              </form>
            )}

            <ul className="space-y-2">
              {data.achievements.map((a) => (
                <li key={a.id} className="k-muted flex items-center justify-between gap-2 p-2.5 text-xs">
                  <div>
                    <div className="font-bold">
                      {a.event_name} ({a.ipc_class}) — <span className="text-sky-700">{a.result_value}</span>
                    </div>
                    <div className="opacity-80">{a.competition_name}</div>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                      a.verification_tier === "organizer_verified"
                        ? "bg-emerald-700 text-white"
                        : a.verification_tier === "coach_verified"
                          ? "bg-sky-700 text-white"
                          : "bg-amber-200 text-amber-950"
                    }`}
                  >
                    {trMap(TIER_LABELS, a.verification_tier, lang)}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* 2-Layer Privacy Control */}
          <section className="k-card space-y-2.5 p-5" aria-labelledby="priv-h">
            <h2 id="priv-h" className="flex items-center gap-2 text-base font-bold">
              <Shield className="h-5 w-5 text-emerald-700" aria-hidden="true" />
              {t.passportPrivacyTitle}
            </h2>
            <p className="text-xs leading-relaxed opacity-90">
              {data.passport_public ? t.passportPublicDesc : t.passportPrivateDesc}
            </p>
            <button
              type="button"
              onClick={handleTogglePrivacy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-400 px-3 py-2 text-xs font-bold hover:bg-slate-100"
            >
              <Lock className="h-3.5 w-3.5" aria-hidden="true" />
              {data.passport_public ? t.switchToPrivate : t.switchToPublic}
            </button>
          </section>
        </div>
      </div>

      {/* Warning Icon unused fallback guard */}
      <span className="sr-only">
        <AlertTriangle />
      </span>
    </div>
  );
}
