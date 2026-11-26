from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

FORBIDDEN_SCOUT_KEYS = {
    "risk",
    "risk_level",
    "acwr",
    "load",
    "load_summary",
    "load_zone",
    "acute_load_7d",
    "chronic_weekly_avg_28d",
    "wow_change_pct",
    "shoulder",
    "injury",
    "fatigue",
    "findings",
    "findings_json",
    "baseline_deltas",
    "baseline_deltas_json",
    "cue_en",
    "cue_ar",
    "coach_notes",
}


def _collect_keys_and_strings(obj, keys: set[str], strings: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k).lower())
            _collect_keys_and_strings(v, keys, strings)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys_and_strings(item, keys, strings)
    elif isinstance(obj, str):
        strings.append(obj.lower())


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_roles_and_seeded_demo_accounts(client: TestClient):
    r = client.get("/api/auth/demo-accounts")
    assert r.status_code == 200
    accounts = r.json()
    assert len(accounts) >= 6
    emails = {a["email"] for a in accounts}
    assert {"tariq.t54@kinetiq.demo", "coach@kinetiq.demo", "scout@kinetiq.demo"}.issubset(emails)


def test_two_layer_privacy_boundary_and_leak_guard(client: TestClient):
    scout_hdr = _login(client, "scout@kinetiq.demo")

    # 1. Scout is forbidden from private health/coach/clip endpoints
    assert client.get("/api/coach/readiness", headers=scout_hdr).status_code == 403
    assert client.get("/api/athlete/me/dashboard", headers=scout_hdr).status_code == 403
    assert client.get("/api/sessions", headers=scout_hdr).status_code == 403
    assert client.get("/api/clips/1", headers=scout_hdr).status_code == 403

    # 2. Walk every Scout endpoint response and assert ZERO forbidden health/risk keys leak
    for url, method, payload in [
        ("/api/scout/passports", "GET", None),
        ("/api/scout/passports/1", "GET", None),
        ("/api/scout/nl-search", "POST", {"query": "verified T54 400m under 52s"}),
    ]:
        r = client.get(url, headers=scout_hdr) if method == "GET" else client.post(url, headers=scout_hdr, json=payload)
        assert r.status_code == 200, r.text
        keys: set[str] = set()
        strings: list[str] = []
        _collect_keys_and_strings(r.json(), keys, strings)
        leaked_keys = [k for k in keys if any(bad in k for bad in ("risk", "acwr", "load", "shoulder", "injury", "fatigue", "finding", "baseline_delta", "cue_en", "cue_ar", "coach_note"))]
        assert not leaked_keys, f"Privacy leak in {url}: {leaked_keys}"
        for s in strings:
            assert "rotator-cuff" not in s and "impingement" not in s and "red-zone" not in s


def test_end_to_end_demo_clip_analysis_wheelchair_and_guide_sync(client: TestClient):
    tariq_hdr = _login(client, "tariq.t54@kinetiq.demo")
    r = client.post(
        "/api/clips/analyze-demo",
        headers=tariq_hdr,
        json={"module_type": "wheelchair_propulsion", "scenario": "fatigue_spike"},
    )
    assert r.status_code == 200, r.text
    clip = r.json()
    assert clip["status"] == "completed"
    assert clip["overlay_url"].startswith("/api/media/")
    assert len(clip["keyframe_urls"]) >= 3
    assert clip["cue_en"] and clip["cue_ar"]
    assert clip["risk_level"] in ("red", "amber")

    # Verify overlay MP4 actually serves
    media_r = client.get(clip["overlay_url"])
    assert media_r.status_code == 200
    assert len(media_r.content) > 1000

    # Test T12 guide-runner sync stretch module
    layla_hdr = _login(client, "layla.t12@kinetiq.demo")
    r2 = client.post(
        "/api/clips/analyze-demo",
        headers=layla_hdr,
        json={"module_type": "guide_runner_sync", "scenario": "optimal_baseline"},
    )
    assert r2.status_code == 200, r2.text
    gclip = r2.json()
    assert gclip["status"] == "completed"
    assert gclip["metrics_json"].get("dual_pose_detected") is True
    assert "guide_stride_sync_pct" in gclip["metrics_json"]["metrics"]


def test_baseline_building_for_new_athlete_t40(client: TestClient):
    omar_hdr = _login(client, "omar.t40@kinetiq.demo")
    r = client.post(
        "/api/clips/analyze-demo",
        headers=omar_hdr,
        json={"module_type": "standing_para_gait", "scenario": "fatigue_spike"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["risk_level"] == "baseline_building"


def test_coach_session_load_verification_and_scout_pdf(client: TestClient):
    coach_hdr = _login(client, "coach@kinetiq.demo")
    scout_hdr = _login(client, "scout@kinetiq.demo")

    # Coach readiness dashboard
    dash = client.get("/api/coach/readiness", headers=coach_hdr)
    assert dash.status_code == 200
    athletes = dash.json()
    assert len(athletes) >= 5
    tariq = next(a for a in athletes if a["ipc_class"] == "T54")
    assert tariq["load_summary"]["load_zone"] == "red"

    # Coach logs squad session
    sess_r = client.post(
        "/api/sessions",
        headers=coach_hdr,
        json={
            "title": "Pre-Meet T54 Taper Push",
            "event_group": "Wheelchair T51-T54",
            "limb_load_type": "upper_limb",
            "session_date": date.today().isoformat(),
            "duration_min": 30,
            "distance_m": 1400,
            "intensity_rpe": 6,
            "attendee_ids": [tariq["athlete_id"]],
        },
    )
    assert sess_r.status_code == 200
    assert sess_r.json()["attendee_count"] == 1

    # Coach verifies Tariq's 50.84s 400m PB
    unverified_400 = next(a for a in tariq["achievements"] if a["event_name"] == "400m")
    ver_r = client.patch(
        f"/api/achievements/{unverified_400['id']}/verify",
        headers=coach_hdr,
        json={"verification_tier": "coach_verified"},
    )
    assert ver_r.status_code == 200
    assert ver_r.json()["verification_tier"] == "coach_verified"

    # Bilingual NL Scout search (EN & AR)
    nl_en = client.post("/api/scout/nl-search", headers=scout_hdr, json={"query": "verified T54 400m under 52s"})
    assert nl_en.status_code == 200
    assert any(p["ipc_class"] == "T54" for p in nl_en.json()["results"])

    nl_ar = client.post("/api/scout/nl-search", headers=scout_hdr, json={"query": "متسابقي كراسي متحركة T54 موثق"})
    assert nl_ar.status_code == 200
    assert any(p["ipc_class"] == "T54" for p in nl_ar.json()["results"])

    # Accessible PDF Passport export
    pdf_r = client.get(f"/api/scout/passports/{tariq['athlete_id']}/pdf", headers=scout_hdr)
    assert pdf_r.status_code == 200
    assert pdf_r.headers["content-type"] == "application/pdf"
    assert pdf_r.content.startswith(b"%PDF-")
