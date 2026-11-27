"use client";

import { useState } from "react";
import { Award, CheckCircle2, Download, Search, ShieldCheck, Sparkles, Star, Volume2 } from "lucide-react";
import { apiFetch, downloadPassportPdf, mediaUrl, ScoutPassportView } from "@/lib/api";
import { COUNTRY_LABELS, DICT, Lang, TIER_LABELS, trMap } from "@/lib/i18n";

interface ScoutViewProps {
  initialPassports: ScoutPassportView[];
  token: string;
  lang: Lang;
  onSpeak: (text: string, speakLang?: Lang) => void;
  onAnnounce: (msg: string) => void;
}

export function ScoutView({
  initialPassports,
  token,
  lang,
  onSpeak,
  onAnnounce,
}: ScoutViewProps) {
  const t = DICT[lang];
  const [passports, setPassports] = useState<ScoutPassportView[]>(initialPassports);
  const [nlQuery, setNlQuery] = useState("");
  const [interpreted, setInterpreted] = useState<Record<string, unknown> | null>(null);
  const [ipcFilter, setIpcFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  async function applyStructuredFilters(ipc: string, ev: string, ver: boolean) {
    const params = new URLSearchParams();
    if (ipc) params.set("ipc_class", ipc);
    if (ev) params.set("event", ev);
    if (ver) params.set("verified_only", "true");
    const res = await apiFetch<ScoutPassportView[]>(`/api/scout/passports?${params.toString()}`, {}, token);
    setPassports(res);
    setInterpreted(null);
  }

  async function runNlSearch(queryText: string) {
    if (!queryText.trim()) return;
    setNlQuery(queryText);
    const res = await apiFetch<{
      query: string;
      interpreted_filters: Record<string, unknown>;
      translation_source: string;
      results: ScoutPassportView[];
    }>("/api/scout/nl-search", { method: "POST", body: JSON.stringify({ query: queryText }) }, token);
    setPassports(res.results);
    setInterpreted(res.interpreted_filters);
    onAnnounce(`Found ${res.results.length} verified Para-athlete passport(s).`);
  }

  async function handleShortlist(athleteId: number, requestContact: boolean) {
    await apiFetch(
      `/api/scout/shortlist/${athleteId}`,
      {
        method: "POST",
        body: JSON.stringify({
          note: "Shortlisted via ATSN'26 KinetiQ Para NPC Selector View",
          contact_requested: requestContact,
        }),
      },
      token
    );
    setPassports((prev) =>
      prev.map((p) =>
        p.athlete_id === athleteId
          ? { ...p, shortlisted: true, contact_requested: p.contact_requested || requestContact }
          : p
      )
    );
    onAnnounce(requestContact ? "Contact request sent to athlete's coach." : "Athlete added to shortlist.");
  }

  return (
    <div className="space-y-6">
      {/* 2-Layer Privacy Enforcement Banner */}
      <div className="flex items-start gap-3 rounded-xl border-2 border-emerald-600 bg-emerald-50 p-4 text-sm text-emerald-950">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" aria-hidden="true" />
        <p className="font-semibold">{t.scoutPrivacyShield}</p>
      </div>

      {/* Natural Language + Structured Search */}
      <section className="k-card space-y-4 p-5" aria-labelledby="scout-h">
        <h1 id="scout-h" className="flex items-center gap-2 text-xl font-extrabold">
          <Sparkles className="h-5 w-5 text-sky-700" aria-hidden="true" />
          {t.scoutSearchTitle}
        </h1>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            runNlSearch(nlQuery);
          }}
          className="flex flex-wrap gap-2"
        >
          <input
            value={nlQuery}
            onChange={(e) => setNlQuery(e.target.value)}
            placeholder={t.nlPlaceholder}
            aria-label="Natural language scout search"
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900"
          />
          <button
            type="submit"
            className="k-btn-primary inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-bold"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
            {t.nlSearchBtn}
          </button>
          <button
            type="button"
            onClick={() => {
              setNlQuery("");
              setIpcFilter("");
              setEventFilter("");
              setVerifiedOnly(false);
              applyStructuredFilters("", "", false);
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold hover:bg-slate-100"
          >
            {t.clearFilters}
          </button>
        </form>

        {/* Quick Bilingual NL Examples */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold opacity-75">{t.quickAiQueries}</span>
          {(lang === "ar"
            ? [
                "متسابقي كراسي متحركة T54 موثق",
                "عداء T64 100m أقل من 12 ثانية",
                "إعاقة بصرية T12",
                "verified T54 400m under 52s",
              ]
            : [
                "verified T54 400m under 52s",
                "متسابقي كراسي متحركة T54 موثق",
                "verified T64 100m under 12s",
                "visually impaired T12",
              ]
          ).map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => runNlSearch(q)}
              className="rounded-full border border-sky-300 bg-sky-50 px-3 py-1 font-semibold text-sky-900 hover:bg-sky-100"
            >
              {q}
            </button>
          ))}
        </div>

        {interpreted && (
          <div className="rounded-md bg-slate-900 px-3 py-2 font-mono text-xs text-sky-200" dir="ltr">
            {t.interpretedFilters} {JSON.stringify(interpreted)}
          </div>
        )}

        {/* Structured Filters */}
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3 text-xs">
          <select
            aria-label={t.allIpcClasses}
            value={ipcFilter}
            onChange={(e) => {
              setIpcFilter(e.target.value);
              applyStructuredFilters(e.target.value, eventFilter, verifiedOnly);
            }}
            className="rounded border border-slate-300 bg-white px-2.5 py-1.5 text-slate-900"
          >
            <option value="">{t.allIpcClasses}</option>
            <option value="T54">{t.clsT54}</option>
            <option value="T64">{t.clsT64}</option>
            <option value="T12">{t.clsT12}</option>
            <option value="T37">{t.clsT37}</option>
            <option value="T40">{t.clsT40}</option>
          </select>

          <select
            aria-label={t.allEvents}
            value={eventFilter}
            onChange={(e) => {
              setEventFilter(e.target.value);
              applyStructuredFilters(ipcFilter, e.target.value, verifiedOnly);
            }}
            className="rounded border border-slate-300 bg-white px-2.5 py-1.5 text-slate-900"
          >
            <option value="">{t.allEvents}</option>
            <option value="100m">100m</option>
            <option value="200m">200m</option>
            <option value="400m">400m</option>
            <option value="800m">800m</option>
          </select>

          <label className="inline-flex items-center gap-1.5 font-semibold">
            <input
              type="checkbox"
              checked={verifiedOnly}
              onChange={(e) => {
                setVerifiedOnly(e.target.checked);
                applyStructuredFilters(ipcFilter, eventFilter, e.target.checked);
              }}
            />
            {t.verifiedOnlyLabel}
          </label>
        </div>
      </section>

      {/* Verified Para-Athlete Passport Grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {passports.map((p) => (
          <article key={p.athlete_id} className="k-card flex flex-col justify-between space-y-4 p-5">
            <div className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-[#1b365d] px-3 py-0.5 text-xs font-bold text-white">
                      IPC {p.ipc_class}
                    </span>
                    <span className="text-xs font-semibold text-slate-600">
                      {trMap(COUNTRY_LABELS, p.country, lang)}
                    </span>
                    {p.is_demo_data && (
                      <span className="rounded bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                        {t.demoData}
                      </span>
                    )}
                  </div>
                  <h2 className="mt-1.5 text-lg font-extrabold">
                    {lang === "ar" ? p.full_name_ar : p.full_name}
                  </h2>
                  <p className="text-xs text-slate-600">
                    {lang === "ar" ? p.affiliation_ar : p.affiliation} · {p.primary_events.join(", ")}
                  </p>
                </div>

                <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-1.5 text-center text-sky-950">
                  <div className="text-[10px] font-bold uppercase">{t.formConsistency}</div>
                  <div className="text-lg font-black">{p.form_consistency_score}/100</div>
                </div>
              </div>

              {/* Bilingual AI Scouting Summary */}
              <div className="k-muted space-y-2 p-3 text-xs leading-relaxed">
                <p>{lang === "ar" ? p.ai_scout_summary_ar : p.ai_scout_summary_en}</p>
                <button
                  type="button"
                  onClick={() => onSpeak(lang === "ar" ? p.ai_scout_summary_ar : p.ai_scout_summary_en, lang)}
                  className="inline-flex items-center gap-1 font-bold text-teal-800 hover:underline"
                >
                  <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
                  {t.listenCue}
                </button>
              </div>

              {/* Verified Achievements */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-bold">
                  <span className="flex items-center gap-1">
                    <Award className="h-4 w-4 text-amber-600" aria-hidden="true" /> {t.competitionResults}
                  </span>
                  <span className="text-emerald-800">
                    {p.coach_confirmed_sessions_30d} {t.confirmedSessions30d}
                  </span>
                </div>
                {p.achievements.map((a) => (
                  <div key={a.id} className="flex items-center justify-between rounded border border-slate-200 px-2.5 py-1.5 text-xs">
                    <span>
                      <strong>{a.event_name}</strong>: {a.result_value} · <span className="opacity-75">{a.competition_name}</span>
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                        a.verification_tier === "organizer_verified"
                          ? "bg-emerald-700 text-white"
                          : a.verification_tier === "coach_verified"
                            ? "bg-sky-700 text-white"
                            : "bg-amber-200 text-amber-950"
                      }`}
                    >
                      {trMap(TIER_LABELS, a.verification_tier, lang)}
                    </span>
                  </div>
                ))}
              </div>

              {/* Curated Track Clip Preview (zero private risk data!) */}
              {p.curated_clips[0]?.overlay_url && (
                <video
                  src={mediaUrl(p.curated_clips[0].overlay_url)}
                  controls
                  playsInline
                  className="h-44 w-full rounded-lg border border-slate-300 bg-slate-950 object-contain"
                  aria-label={`Curated track clip for ${p.full_name}`}
                />
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-3">
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => handleShortlist(p.athlete_id, false)}
                  className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-bold ${
                    p.shortlisted
                      ? "bg-amber-400 text-black"
                      : "border border-slate-400 hover:bg-slate-100"
                  }`}
                >
                  <Star className="h-3.5 w-3.5" aria-hidden="true" />
                  {p.shortlisted ? t.shortlistedLabel : t.shortlistBtn}
                </button>
                <button
                  type="button"
                  onClick={() => handleShortlist(p.athlete_id, true)}
                  className="inline-flex items-center gap-1 rounded-md border border-sky-600 px-3 py-1.5 text-xs font-bold text-sky-800 hover:bg-sky-50"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  {p.contact_requested ? t.contactRequestedLabel : t.requestContactBtn}
                </button>
              </div>
              <button
                type="button"
                onClick={() => downloadPassportPdf(p.athlete_id, token)}
                className="k-btn-primary inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-bold"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                {t.downloadPdfBtn}
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
