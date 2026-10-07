"""Frost & Sow planner — Gemma 4 tip + TabPFN ranking, stdlib stub fallback."""

import csv, hashlib, os
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
CROPS_CSV = DATA / "crops.csv"
FROST_CSV = DATA / "frost.csv"
HISTORY_CSV = DATA / "history.csv"
FEATS = ["sun_match", "weeks_fit", "harvest_fit", "experience", "month"]
LVL = {"new": 0, "some": 1, "green": 2}
_MODEL = None  # cached TabPFN model; False when unavailable


def _load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _frost_for(pincode):
    rows = _load(FROST_CSV)
    prefix = (pincode or "").strip()[:2]
    hit = next((r for r in rows if r["pincode_prefix"].strip() == prefix), None)
    return hit or next((r for r in rows if r["pincode_prefix"].strip() == "*"), rows[0])


def _weeks_left(first, today):
    try:
        if first.strip().upper() == "NA":
            return 52
        m, d = map(int, first.strip().split("-"))
        tgt = date(today.year, m, d)
        if tgt < today:
            tgt = date(today.year + 1, m, d)
        return max((tgt - today).days // 7, 0)
    except ValueError:
        return 0


def _shift(mmdd, days, today):
    try:
        m, d = map(int, mmdd.strip().split("-"))
        base = date(today.year, m, d) + timedelta(days=days)
        return base.strftime("%m-%d")
    except ValueError:
        return mmdd


def _candidates(crops, sun, ulvl, mins, wl):
    tol = lambda c: [t.strip() for t in c["sun"].split(",")]  # noqa: E731
    base = [
        c
        for c in crops
        if sun in tol(c) and LVL.get(c["difficulty"].strip().lower(), 0) <= ulvl
    ]
    if mins < 30:  # low care time -> easy crops only
        base = [c for c in base if c["difficulty"].strip().lower() == "new"] or base
    return [c for c in base if int(c["weeks_before_frost"]) <= wl] or base


def _try_tabpfn(rows):
    """Score rows via TabPFN on history.csv, or None. Lazy import, cached fit."""
    global _MODEL
    try:
        if _MODEL is None:
            from tabpfn import TabPFNClassifier

            hist = _load(HISTORY_CSV)
            X = [[float(r[f]) for f in FEATS] for r in hist]
            _MODEL = TabPFNClassifier(device="cpu")
            _MODEL.fit(X, [int(r["success"]) for r in hist])
        if _MODEL is False:
            return None
        return [round(float(p[1]), 4) for p in _MODEL.predict_proba(rows)]
    except Exception:
        _MODEL = False  # tabpfn missing/broken -> stick to the stub
        return None


def rank_crops(rows):
    """(scores, used_tabpfn) — TabPFN ranking with silent stub fallback."""
    try:
        scores = _try_tabpfn(rows)
    except Exception:
        scores = None
    if scores is None:  # weighted stdlib stub on the same features
        w = lambda r: round(0.4 * r[0] + 0.3 * r[1] + 0.2 * r[2] + 0.05 * r[3], 4)  # noqa: E731
        return [w(r) for r in rows], False
    return scores, True


def _try_gemma(names, sun):
    """One-line tip from Gemma 4, or None. Lazy imports — stdlib only at top."""
    import json
    import urllib.request

    model = os.getenv("GEMMA_MODEL", "gemma4:e2b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    prompt = (
        f"Kitchen-garden coach: {sun} sun, sowing {', '.join(names)}. "
        "Give ONE practical one-line sowing tip grounded in these crops. "
        'Reply with ONLY a JSON object, no other text, like {"tip": "..."}.'
    )
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        outer = json.loads(r.read().decode())
    txt = outer.get("response", "")
    inner = json.loads(txt[txt.index("{") : txt.rindex("}") + 1])
    return str(inner.get("tip", "")).strip() or None


def plan_sowing(
    pincode: str,
    minutes_week: int,
    sun: str,
    experience: str,
    history: list | None = None,
) -> dict:
    """Plan up to 3 crops. Always returns plan_id/crops/tip/frost/spot/used_*."""
    sun = (sun or "full").strip().lower()
    sun = sun if sun in ("full", "partial", "shade") else "full"
    exp = (experience or "new").strip().lower()
    exp = exp if exp in LVL else "new"
    mins = int(minutes_week) if str(minutes_week).isdigit() else 0
    today = date.today()
    fr = _frost_for(str(pincode or ""))
    wl = _weeks_left(fr["first_frost"], today)
    fit = _candidates(_load(CROPS_CSV), sun, LVL[exp], mins, wl)
    rows = []
    for c in fit:
        sm = 1.0 if sun in [t.strip() for t in c["sun"].split(",")] else 0.0
        wf = 1.0 if int(c["weeks_before_frost"]) <= wl else 0.0
        hf = 1.0 if int(c["days_to_harvest"]) <= max(wl * 7, 1) else 0.0
        rows.append([sm, wf, hf, float(LVL[exp]), float(today.month)])
    scores, used_t = rank_crops(rows) if rows else ([], False)
    ranked = sorted(zip(fit, scores), key=lambda p: (-p[1], p[0]["name"]))
    seen = set(history or [])
    unseen = [p for p in ranked if p[0]["name"] not in seen]
    top = (unseen + [p for p in ranked if p[0]["name"] in seen])[:3]
    names = [c["name"] for c, _ in top]
    try:
        gemma_tip = _try_gemma(names, sun) if names else None
    except Exception:
        gemma_tip = None  # Ollama/Gemma absent -> stub tip
    tip = gemma_tip
    if not tip and names:
        c0 = top[0][0]
        tip = f"Sow {names[0]} {c0['spacing']} apart; keep moist, harvest in ~{c0['days_to_harvest']} days."
    first = fr["first_frost"].strip()
    crops = []
    for c, s in top:
        wbf, dth = c["weeks_before_frost"], c["days_to_harvest"]
        sb = "anytime" if first.upper() == "NA" else _shift(first, -int(wbf) * 7, today)
        why = f"Sow {wbf}w pre-frost, {sun} sun, ready {dth}d."
        crops.append({"name": c["name"], "why": why, "sow_by": sb, "score": s})
    raw = f"{pincode}|{mins}|{sun}|{exp}|{','.join(names)}".encode()
    pid = hashlib.sha1(raw).hexdigest()[:12]
    return {
        "plan_id": pid,
        "crops": crops,
        "tip": tip or "No crop fits this window — try more sun or weekly time.",
        "frost": {
            "last_frost": fr["last_frost"].strip(),
            "first_frost": first,
            "weeks_left_in_window": wl,
        },
        "spot": names[0] if names else "",
        "used_gemma": bool(gemma_tip),
        "used_tabpfn": used_t,
    }


if __name__ == "__main__":  # ponytail check: stub self-test, no framework
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # force the stub path
    globals()["_try_tabpfn"] = lambda rows: None  # force stub scores
    a = plan_sowing("110016", 60, "full", "green")
    b = plan_sowing("110016", 60, "full", "green")
    for k in ("plan_id", "crops", "tip", "frost", "spot", "used_gemma", "used_tabpfn"):
        assert k in a, a
    assert a == b and len(a["plan_id"]) == 12  # deterministic stub
    keys = {"name", "why", "sow_by", "score"}
    assert a["crops"] and all(set(c) == keys for c in a["crops"])
    s = plan_sowing("560001", 120, "shade", "green")  # south: year-round window
    suns = {c["name"]: c["sun"] for c in _load(CROPS_CSV)}
    assert s["crops"] and all("shade" in suns[c["name"]] for c in s["crops"]), s
    tiny = _candidates(_load(CROPS_CSV), "full", 2, 120, 4)  # frost filter check
    assert tiny and all(int(c["weeks_before_frost"]) <= 4 for c in tiny), tiny
    assert "tomato" not in [c["name"] for c in tiny]
    assert not a["used_gemma"] and not a["used_tabpfn"]
    print("sow.py stub OK:", a["plan_id"], "->", a["spot"])
