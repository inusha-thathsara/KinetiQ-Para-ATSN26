"use client";

import { useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, ClipboardCheck, ShieldAlert, Volume2 } from "lucide-react";
import { apiFetch, PrivateHealthView } from "@/lib/api";
import { DICT, Lang } from "@/lib/i18n";

interface CoachViewProps {
  squad: PrivateHealthView[];
  token: string;
  lang: Lang;
  onRefresh: () => Promise<void>;
  onSpeak: (text: string, speakLang?: Lang) => void;
  onAnnounce: (msg: string) => void;
}

export function CoachView({
  squad,
  token,
  lang,
  onRefresh,
  onSpeak,
  onAnnounce,
}: CoachViewProps) {
  const t = DICT[lang];
  const [title, setTitle] = useState("Pre-Meet Push Block (6 × 200m + 4 × 400m)");
  const [eventGroup, setEventGroup] = useState("Wheelchair T51-T54");
  const [limbType, setLimbType] = useState<"upper_limb" | "lower_limb">("upper_limb");
  const [duration, setDuration] = useState("60");
  const [distance, setDistance] = useState("2800");
  const [rpe, setRpe] = useState("9");
  const [selectedIds, setSelectedIds] = useState<number[]>(() =>
    squad.filter((a) => a.limb_load_type === "upper_limb").map((a) => a.athlete_id)
  );
  const [submitting, setSubmitting] = useState(false);

  function toggleAttendee(id: number) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function handleLogSession(e: React.FormEvent) {
    e.preventDefault();
    if (selectedIds.length === 0) return;
    setSubmitting(true);
    try {
      await apiFetch(
        "/api/sessions",
        {
          method: "POST",
          body: JSON.stringify({
            title,
            event_group: eventGroup,
            limb_load_type: limbType,
            session_date: new Date().toISOString().slice(0, 10),
            duration_min: parseFloat(duration) || 45,
            distance_m: parseFloat(distance) || 0,
            intensity_rpe: parseFloat(rpe) || 7,
            attendee_ids: selectedIds,
          }),
        },
        token
      );
      await onRefresh();
      onAnnounce("Squad session logged and ACWR recalculated in 1 click.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify(achievementId: number, tier: "coach_verified" | "organizer_verified") {
    await apiFetch(
      `/api/achievements/${achievementId}/verify`,
      { method: "PATCH", body: JSON.stringify({ verification_tier: tier }) },
      token
    );
    await onRefresh();
    onAnnounce(`Achievement approved as ${tier.replace("_", " ")} and Scout Passport updated.`);
  }

  async function handleAddTaperNote(athleteId: number) {
    await apiFetch(
      "/api/coach/notes",
      {
        method: "POST",
        body: JSON.stringify({
          athlete_id: athleteId,
          load_adjustment: "taper_20pct",
          note_text: "Reduced next high-intensity push block by 20% following combined shoulder + volume spike flag.",
        }),
      },
      token
    );
    await onRefresh();
    onAnnounce("Load taper note logged for athlete.");
  }

  const pendingAchievements = squad.flatMap((a) =>
    a.achievements
      .filter((ach) => ach.verification_tier === "self_reported")
      .map((ach) => ({ athlete: a, ach }))
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Squad Readiness Table */}
        <section className="k-card space-y-4 p-5 lg:col-span-8" aria-labelledby="coach-h">
          <h1 id="coach-h" className="flex items-center gap-2 text-xl font-extrabold">
            <ShieldAlert className="h-5 w-5 text-rose-600" aria-hidden="true" />
            {t.coachSquadTitle}
          </h1>

          <div className="space-y-3">
            {squad.map((a) => {
              const zone = a.load_summary.overall_zone;
              const badgeCls =
                zone === "red"
                  ? "bg-rose-700 text-white"
                  : zone === "amber"
                    ? "bg-amber-500 text-black"
                    : "bg-emerald-700 text-white";
              return (
                <article key={a.athlete_id} className="k-muted space-y-2.5 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-[#1b365d] px-2.5 py-0.5 text-xs font-bold text-white">
                        {a.ipc_class}
                      </span>
                      <h2 className="text-base font-bold">
                        {lang === "ar" ? a.full_name_ar : a.full_name}
                      </h2>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase ${badgeCls}`}>
                        {zone} · {a.load_summary.readiness_score}/100
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs font-semibold">
                      <span>ACWR: {a.load_summary.acwr}</span>
                      <span>
                        WoW: {a.load_summary.wow_change_pct > 0 ? "+" : ""}
                        {a.load_summary.wow_change_pct}%
                      </span>
                      <span className="rounded bg-white px-2 py-0.5 text-slate-800">
                        {lang === "ar"
                          ? a.load_summary.clip_freshness.label_ar
                          : a.load_summary.clip_freshness.label_en}
                      </span>
                    </div>
                  </div>

                  <p className="text-sm font-medium">
                    {zone === "red" && (
                      <AlertTriangle className="me-1.5 inline h-4 w-4 text-rose-600" aria-hidden="true" />
                    )}
                    {lang === "ar" ? a.load_summary.combined_reason_ar : a.load_summary.combined_reason_en}
                  </p>

                  {a.latest_clip && (
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-300/70 pt-2 text-xs">
                      <span>
                        Latest Clip Score: <strong>{a.latest_clip.form_score}/100</strong> · Confidence:{" "}
                        <strong>{Math.round(a.latest_clip.detection_confidence * 100)}%</strong>
                      </span>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            onSpeak(lang === "ar" ? a.latest_clip!.cue_ar : a.latest_clip!.cue_en, lang)
                          }
                          className="inline-flex items-center gap-1 rounded border border-teal-700 bg-white px-2.5 py-1 font-semibold text-teal-900 hover:bg-teal-50"
                        >
                          <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
                          {t.listenCue}
                        </button>
                        {zone !== "green" && (
                          <button
                            type="button"
                            onClick={() => handleAddTaperNote(a.athlete_id)}
                            className="k-btn-primary rounded px-2.5 py-1 font-semibold"
                          >
                            {t.addTaperNoteBtn}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>

        {/* Right Column: 1-Click Squad Logger + Verification Queue */}
        <div className="space-y-6 lg:col-span-4">
          <section className="k-card space-y-3 p-5" aria-labelledby="log-sess-h">
            <h2 id="log-sess-h" className="flex items-center gap-2 text-base font-bold">
              <Activity className="h-5 w-5 text-sky-700" aria-hidden="true" />
              {t.logSessionTitle}
            </h2>
            <form onSubmit={handleLogSession} className="space-y-3 text-xs">
              <label className="block font-semibold">
                Workout Title
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900"
                  required
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block font-semibold">
                  Load Series
                  <select
                    value={limbType}
                    onChange={(e) => {
                      const v = e.target.value as "upper_limb" | "lower_limb";
                      setLimbType(v);
                      setEventGroup(v === "upper_limb" ? "Wheelchair T51-T54" : "Standing T11-T64");
                      setSelectedIds(squad.filter((a) => a.limb_load_type === v).map((a) => a.athlete_id));
                    }}
                    className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900"
                  >
                    <option value="upper_limb">Upper-Limb (Wheelchair)</option>
                    <option value="lower_limb">Lower-Limb (Standing/VI)</option>
                  </select>
                </label>
                <label className="block font-semibold">
                  Intensity RPE (1–10)
                  <input
                    type="number"
                    min="1"
                    max="10"
                    step="0.5"
                    value={rpe}
                    onChange={(e) => setRpe(e.target.value)}
                    className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900"
                  />
                </label>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <label className="block font-semibold">
                  Duration (min)
                  <input
                    type="number"
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                    className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900"
                  />
                </label>
                <label className="block font-semibold">
                  Distance (m)
                  <input
                    type="number"
                    value={distance}
                    onChange={(e) => setDistance(e.target.value)}
                    className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-slate-900"
                  />
                </label>
              </div>

              <fieldset className="space-y-1">
                <legend className="font-semibold">1-Click Attendance</legend>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {squad.map((a) => {
                    const checked = selectedIds.includes(a.athlete_id);
                    return (
                      <button
                        key={a.athlete_id}
                        type="button"
                        aria-pressed={checked}
                        onClick={() => toggleAttendee(a.athlete_id)}
                        className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${
                          checked
                            ? "border-sky-700 bg-sky-700 text-white"
                            : "border-slate-300 bg-white text-slate-800"
                        }`}
                      >
                        {a.ipc_class} {a.full_name.split(" ")[0]}
                      </button>
                    );
                  })}
                </div>
              </fieldset>

              <button
                type="submit"
                disabled={submitting || selectedIds.length === 0}
                className="k-btn-primary w-full rounded-md py-2 text-xs font-bold disabled:opacity-50"
              >
                {t.logSessionBtn}
              </button>
            </form>
          </section>

          {/* Pending PB Verifications */}
          <section className="k-card space-y-3 p-5" aria-labelledby="ver-h">
            <h2 id="ver-h" className="flex items-center gap-2 text-base font-bold">
              <ClipboardCheck className="h-5 w-5 text-emerald-700" aria-hidden="true" />
              {t.pendingVerifications} ({pendingAchievements.length})
            </h2>
            {pendingAchievements.length === 0 ? (
              <p className="flex items-center gap-1.5 text-xs text-emerald-800">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> All submitted PBs are verified.
              </p>
            ) : (
              <div className="space-y-3">
                {pendingAchievements.map(({ athlete, ach }) => (
                  <div key={ach.id} className="k-muted space-y-2 p-3 text-xs">
                    <div className="font-bold">
                      {athlete.full_name} ({ach.ipc_class}) — {ach.event_name}:{" "}
                      <span className="text-sky-700">{ach.result_value}</span>
                    </div>
                    <div className="opacity-85">
                      {ach.competition_name} · Proof: <code>{ach.proof_reference || "attached"}</code>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleVerify(ach.id, "coach_verified")}
                        className="rounded bg-sky-700 px-2.5 py-1.5 font-bold text-white hover:bg-sky-600"
                      >
                        {t.verifyCoachBtn}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleVerify(ach.id, "organizer_verified")}
                        className="rounded bg-emerald-700 px-2.5 py-1.5 font-bold text-white hover:bg-emerald-600"
                      >
                        {t.verifyOrgBtn}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
