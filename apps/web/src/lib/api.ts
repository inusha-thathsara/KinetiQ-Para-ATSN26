export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface UserSummary {
  id: number;
  email: string;
  full_name: string;
  full_name_ar: string;
  role: "athlete" | "coach" | "scout";
  country: string;
  affiliation: string;
  affiliation_ar: string;
  athlete_id: number | null;
  ipc_class: string | null;
}

export interface DemoAccount {
  email: string;
  password: string;
  full_name: string;
  full_name_ar: string;
  role: "athlete" | "coach" | "scout";
  ipc_class: string | null;
  disability_category: string | null;
}

export interface Achievement {
  id: number;
  event_name: string;
  ipc_class: string;
  result_value: string;
  result_seconds: number;
  competition_name: string;
  achieved_date: string;
  proof_reference: string;
  verification_tier: "self_reported" | "coach_verified" | "organizer_verified";
  is_pb: boolean;
}

export interface PrivateClip {
  id: number;
  athlete_id: number;
  module_type: string;
  status: string;
  error_message: string;
  witness_badge: string;
  recorded_at: string;
  overlay_url: string | null;
  keyframe_urls: string[];
  detection_confidence: number;
  form_score: number;
  metrics_json: Record<string, unknown>;
  baseline_deltas_json: Record<
    string,
    {
      current: number;
      baseline_median: number;
      delta: number;
      delta_display?: string;
      z_score: number;
      unit: string;
      status: string;
      sample_count: number;
      label_en: string;
      label_ar: string;
    }
  >;
  risk_level: string;
  findings_json: Array<{
    metric: string;
    severity: string;
    title_en: string;
    title_ar: string;
    z_score: number;
  }>;
  cue_en: string;
  cue_ar: string;
  confidence_note_en: string;
  confidence_note_ar: string;
  ai_source: string;
  is_curated_for_passport: boolean;
  is_demo_sample: boolean;
}

export interface PrivateHealthView {
  athlete_id: number;
  full_name: string;
  full_name_ar: string;
  ipc_class: string;
  disability_category: string;
  limb_load_type: string;
  primary_events: string[];
  passport_public: boolean;
  is_demo_data: boolean;
  load_summary: {
    limb_load_type: string;
    acute_load_7d: number;
    chronic_weekly_avg_28d: number;
    acwr: number;
    wow_change_pct: number;
    load_zone: string;
    overall_zone: string;
    readiness_score: number;
    sessions_30d: number;
    weekly_series: number[];
    clip_freshness: {
      days_old: number | null;
      freshness_weight: number;
      status: string;
      label_en: string;
      label_ar: string;
    };
    combined_reason_en: string;
    combined_reason_ar: string;
  };
  latest_clip: PrivateClip | null;
  recent_clips: PrivateClip[];
  achievements: Achievement[];
  coach_notes: Array<{
    id: number;
    note_text: string;
    load_adjustment: string;
    created_at: string;
  }>;
  disclaimer_en: string;
  disclaimer_ar: string;
}

export interface ScoutPassportView {
  athlete_id: number;
  full_name: string;
  full_name_ar: string;
  country: string;
  affiliation: string;
  affiliation_ar: string;
  ipc_class: string;
  disability_category: string;
  primary_events: string[];
  bio_en: string;
  bio_ar: string;
  is_demo_data: boolean;
  form_consistency_score: number;
  form_trend: Array<{ recorded_date: string; form_score: number }>;
  coach_confirmed_sessions_30d: number;
  achievements: Achievement[];
  curated_clips: Array<{
    id: number;
    module_type: string;
    recorded_at: string;
    overlay_url: string | null;
    witness_badge: string;
    form_score: number;
  }>;
  ai_scout_summary_en: string;
  ai_scout_summary_ar: string;
  shortlisted: boolean;
  contact_requested: boolean;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData) && !headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(errText || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function mediaUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export async function downloadPassportPdf(athleteId: number, token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/scout/passports/${athleteId}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("PDF export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `kinetiq_para_passport_${athleteId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
