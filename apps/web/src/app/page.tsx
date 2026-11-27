"use client";

import { useCallback, useEffect, useState } from "react";
import { Accessibility, Shield, Sparkles, Users } from "lucide-react";
import { AccessibilityBar } from "@/components/AccessibilityBar";
import { AthleteView } from "@/components/AthleteView";
import { CoachView } from "@/components/CoachView";
import { ScoutView } from "@/components/ScoutView";
import {
  apiFetch,
  DemoAccount,
  PrivateHealthView,
  ScoutPassportView,
  UserSummary,
} from "@/lib/api";
import { CATEGORY_LABELS, DICT, Lang, ROLE_LABELS, trMap } from "@/lib/i18n";

export default function HomePage() {
  const [lang, setLang] = useState<Lang>("en");
  const [highContrast, setHighContrast] = useState(false);
  const [fontScale, setFontScale] = useState(100);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [liveMessage, setLiveMessage] = useState("");

  const [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserSummary | null>(null);
  const [athleteData, setAthleteData] = useState<PrivateHealthView | null>(null);
  const [coachSquad, setCoachSquad] = useState<PrivateHealthView[]>([]);
  const [scoutPassports, setScoutPassports] = useState<ScoutPassportView[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const t = DICT[lang];

  // Sync HTML dir, lang, high-contrast class, and font size
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    document.documentElement.classList.toggle("high-contrast", highContrast);
  }, [highContrast]);

  useEffect(() => {
    document.documentElement.style.setProperty("--base-font-size", `${Math.round(16 * (fontScale / 100))}px`);
  }, [fontScale]);

  // Load seeded demo accounts on mount
  useEffect(() => {
    apiFetch<DemoAccount[]>("/api/auth/demo-accounts")
      .then(setDemoAccounts)
      .catch((err) => setError(`Backend unreachable at http://localhost:8000 (${(err as Error).message})`));
  }, []);

  const stopSpeech = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  const speak = useCallback(
    (text: string, targetLang?: Lang) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        setLiveMessage("Speech synthesis not supported in this browser.");
        return;
      }
      const chosenLang = targetLang || lang;
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = chosenLang === "ar" ? "ar-SA" : "en-US";
      const voices = window.speechSynthesis.getVoices();
      const match = voices.find((v) => v.lang.toLowerCase().startsWith(chosenLang));
      if (match) {
        utter.voice = match;
      } else if (chosenLang === "ar") {
        setLiveMessage("Arabic OS voice not installed on this device; speaking with default TTS voice.");
      }
      utter.onstart = () => setIsSpeaking(true);
      utter.onend = () => setIsSpeaking(false);
      utter.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utter);
    },
    [lang]
  );

  const loadRoleData = useCallback(async (activeToken: string, activeUser: UserSummary) => {
    if (activeUser.role === "athlete") {
      const d = await apiFetch<PrivateHealthView>("/api/athlete/me/dashboard", {}, activeToken);
      setAthleteData(d);
    } else if (activeUser.role === "coach") {
      const sq = await apiFetch<PrivateHealthView[]>("/api/coach/readiness", {}, activeToken);
      setCoachSquad(sq);
    } else {
      const pp = await apiFetch<ScoutPassportView[]>("/api/scout/passports", {}, activeToken);
      setScoutPassports(pp);
    }
  }, []);

  async function loginAs(email: string, password = "demo1234") {
    setLoading(true);
    setError(null);
    stopSpeech();
    try {
      const res = await apiFetch<{ access_token: string; user: UserSummary }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
      setUser(res.user);
      await loadRoleData(res.access_token, res.user);
      setLiveMessage(
        lang === "ar"
          ? `تم تسجيل الدخول باسم ${res.user.full_name_ar || res.user.full_name} (${trMap(ROLE_LABELS, res.user.role, "ar")}).`
          : `Signed in as ${res.user.full_name} (${res.user.role}).`
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function handleReadSummary() {
    if (user?.role === "athlete" && athleteData?.latest_clip) {
      const cue = lang === "ar" ? athleteData.latest_clip.cue_ar : athleteData.latest_clip.cue_en;
      const loadMsg =
        lang === "ar"
          ? athleteData.load_summary.combined_reason_ar
          : athleteData.load_summary.combined_reason_en;
      speak(`${loadMsg}. ${cue}`, lang);
      return;
    }
    if (user?.role === "coach" && coachSquad.length > 0) {
      const top = coachSquad[0];
      const msg =
        lang === "ar"
          ? `أعلى أولوية للمتابعة: ${top.full_name_ar}، فئة ${top.ipc_class}. ${top.load_summary.combined_reason_ar}`
          : `Top priority athlete: ${top.full_name}, class ${top.ipc_class}. ${top.load_summary.combined_reason_en}`;
      speak(msg, lang);
      return;
    }
    speak(`${t.brand}. ${t.tagline}`, lang);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <AccessibilityBar
        lang={lang}
        onToggleLang={() => setLang((l) => (l === "en" ? "ar" : "en"))}
        highContrast={highContrast}
        onToggleHighContrast={() => setHighContrast((h) => !h)}
        fontScale={fontScale}
        onAdjustFont={(d) => setFontScale((s) => Math.max(90, Math.min(140, s + d)))}
        isSpeaking={isSpeaking}
        onReadSummary={handleReadSummary}
        onStopSpeech={stopSpeech}
        liveMessage={liveMessage}
        userName={user ? (lang === "ar" ? user.full_name_ar : user.full_name) : null}
        userRole={user?.role}
        onSignOut={() => {
          stopSpeech();
          setToken(null);
          setUser(null);
          setAthleteData(null);
          setCoachSquad([]);
          setScoutPassports([]);
        }}
      />

      <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        {error && (
          <div role="alert" className="mb-4 rounded-lg border-2 border-rose-500 bg-rose-50 p-4 text-sm font-semibold text-rose-900">
            {error}
          </div>
        )}

        {!user || !token ? (
          <div className="space-y-6">
            <section className="k-card p-6">
              <div className="max-w-3xl space-y-2">
                <div className="inline-flex items-center gap-2 rounded-full bg-sky-100 px-3 py-1 text-xs font-bold text-sky-900">
                  <Accessibility className="h-4 w-4" aria-hidden="true" />
                  {t.heroBadge}
                </div>
                <h1 className="text-2xl font-extrabold md:text-3xl">{t.loginHeading}</h1>
                <p className="text-sm opacity-85">{t.loginSub}</p>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
                {demoAccounts.map((acc) => {
                  const roleLabel =
                    acc.role === "athlete"
                      ? t.roleAthlete
                      : acc.role === "coach"
                        ? t.roleCoach
                        : t.roleScout;
                  const accent =
                    acc.role === "coach"
                      ? "border-rose-300"
                      : acc.role === "scout"
                        ? "border-emerald-300"
                        : "border-sky-300";
                  return (
                    <button
                      key={acc.email}
                      type="button"
                      disabled={loading}
                      onClick={() => loginAs(acc.email, acc.password)}
                      className={`k-muted flex flex-col items-start justify-between gap-2 border-2 p-4 text-start transition hover:shadow-md ${accent}`}
                    >
                      <div className="flex w-full items-center justify-between gap-2">
                        <span className="rounded bg-[#1b365d] px-2 py-0.5 text-[11px] font-bold text-white">
                          {roleLabel}
                        </span>
                        {acc.ipc_class && (
                          <span className="rounded-full bg-sky-200 px-2 py-0.5 text-xs font-bold text-sky-950">
                            IPC {acc.ipc_class}
                          </span>
                        )}
                      </div>
                      <div className="text-base font-bold">
                        {lang === "ar" ? acc.full_name_ar : acc.full_name}
                      </div>
                      <div className="text-xs opacity-80">
                        {acc.disability_category
                          ? trMap(CATEGORY_LABELS, acc.disability_category, lang)
                          : acc.email}
                      </div>
                      <span className="mt-1 text-xs font-bold text-sky-700">
                        {t.enterAs} {roleLabel} {lang === "ar" ? "←" : "→"}
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>

            {/* 3 Feature Highlights */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="k-card space-y-1.5 p-4">
                <Sparkles className="h-5 w-5 text-sky-700" aria-hidden="true" />
                <h2 className="text-sm font-bold">{t.feat1Title}</h2>
                <p className="text-xs opacity-85">{t.feat1Desc}</p>
              </div>
              <div className="k-card space-y-1.5 p-4">
                <Shield className="h-5 w-5 text-emerald-700" aria-hidden="true" />
                <h2 className="text-sm font-bold">{t.feat2Title}</h2>
                <p className="text-xs opacity-85">{t.feat2Desc}</p>
              </div>
              <div className="k-card space-y-1.5 p-4">
                <Users className="h-5 w-5 text-teal-700" aria-hidden="true" />
                <h2 className="text-sm font-bold">{t.feat3Title}</h2>
                <p className="text-xs opacity-85">{t.feat3Desc}</p>
              </div>
            </div>
          </div>
        ) : user.role === "athlete" && athleteData ? (
          <AthleteView
            data={athleteData}
            token={token}
            lang={lang}
            onRefresh={() => loadRoleData(token, user)}
            onSpeak={speak}
            onAnnounce={setLiveMessage}
          />
        ) : user.role === "coach" ? (
          <CoachView
            squad={coachSquad}
            token={token}
            lang={lang}
            onRefresh={() => loadRoleData(token, user)}
            onSpeak={speak}
            onAnnounce={setLiveMessage}
          />
        ) : (
          <ScoutView
            initialPassports={scoutPassports}
            token={token}
            lang={lang}
            onSpeak={speak}
            onAnnounce={setLiveMessage}
          />
        )}
      </main>
    </div>
  );
}
