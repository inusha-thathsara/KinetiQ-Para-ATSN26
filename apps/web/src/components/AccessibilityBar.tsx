"use client";

import { Contrast, Globe, LogOut, Minus, Plus, Square, Volume2 } from "lucide-react";
import { DICT, Lang } from "@/lib/i18n";

interface AccessibilityBarProps {
  lang: Lang;
  onToggleLang: () => void;
  highContrast: boolean;
  onToggleHighContrast: () => void;
  fontScale: number;
  onAdjustFont: (delta: number) => void;
  isSpeaking: boolean;
  onReadSummary: () => void;
  onStopSpeech: () => void;
  liveMessage: string;
  userName?: string | null;
  userRole?: string | null;
  onSignOut?: () => void;
}

export function AccessibilityBar({
  lang,
  onToggleLang,
  highContrast,
  onToggleHighContrast,
  fontScale,
  onAdjustFont,
  isSpeaking,
  onReadSummary,
  onStopSpeech,
  liveMessage,
  userName,
  userRole,
  onSignOut,
}: AccessibilityBarProps) {
  const t = DICT[lang];

  return (
    <header className="sticky top-0 z-40 border-b border-slate-300 bg-[#1b365d] text-white shadow-sm">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:start-2 focus:z-50 focus:rounded focus:bg-amber-400 focus:px-3 focus:py-2 focus:font-bold focus:text-black"
      >
        {t.skipToMain}
      </a>

      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-400 font-black text-slate-950">
            KQ
          </div>
          <div>
            <p className="text-base font-bold leading-tight">{t.brand}</p>
            <p className="text-xs text-sky-100">{t.tagline}</p>
          </div>
        </div>

        <nav aria-label="Accessibility and Language Controls" className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onToggleLang}
            className="inline-flex items-center gap-1.5 rounded-md border border-sky-300/60 bg-slate-900/40 px-3 py-1.5 text-xs font-semibold hover:bg-sky-700"
          >
            <Globe className="h-3.5 w-3.5" aria-hidden="true" />
            {t.langToggle}
          </button>

          <button
            type="button"
            aria-pressed={highContrast}
            onClick={onToggleHighContrast}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold ${
              highContrast
                ? "border-amber-300 bg-amber-400 text-black"
                : "border-sky-300/60 bg-slate-900/40 text-white hover:bg-sky-700"
            }`}
          >
            <Contrast className="h-3.5 w-3.5" aria-hidden="true" />
            {t.highContrast}
          </button>

          <div className="inline-flex items-center rounded-md border border-sky-300/60 bg-slate-900/40">
            <button
              type="button"
              aria-label={t.fontSmaller}
              onClick={() => onAdjustFont(-10)}
              className="px-2 py-1.5 hover:bg-sky-700"
            >
              <Minus className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
            <span className="px-2 text-xs font-semibold" aria-label="Text size">
              {fontScale}%
            </span>
            <button
              type="button"
              aria-label={t.fontLarger}
              onClick={() => onAdjustFont(10)}
              className="px-2 py-1.5 hover:bg-sky-700"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>

          {isSpeaking ? (
            <button
              type="button"
              onClick={onStopSpeech}
              className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-rose-500"
            >
              <Square className="h-3.5 w-3.5" aria-hidden="true" />
              {t.stopAudio}
            </button>
          ) : (
            <button
              type="button"
              onClick={onReadSummary}
              className="inline-flex items-center gap-1.5 rounded-md bg-teal-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-teal-500"
            >
              <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />
              {t.readPage}
            </button>
          )}

          {userName && onSignOut && (
            <button
              type="button"
              onClick={onSignOut}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/40 px-3 py-1.5 text-xs font-semibold hover:bg-white/10"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              {t.signOut} ({userRole})
            </button>
          )}
        </nav>
      </div>

      {/* Screen-reader live status region */}
      <div
        role="status"
        aria-live="polite"
        className="border-t border-white/15 bg-slate-950/50 px-4 py-1 text-xs text-sky-100"
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-2">
          <span>{liveMessage || t.demoBanner}</span>
          {userName && <span className="font-semibold text-amber-300">{userName}</span>}
        </div>
      </div>
    </header>
  );
}
