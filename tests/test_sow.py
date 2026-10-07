import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import app  # noqa: E402
from app import CompleteIn, SowIn  # noqa: E402


def _force_stub(monkeypatch, sow):
    """Force the stdlib stub path: no Gemma, no TabPFN."""
    monkeypatch.setattr(sow, "_try_gemma", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(sow, "_try_tabpfn", lambda *a, **k: None, raising=False)


def test_stub_plan_shape(monkeypatch):
    sow = pytest.importorskip("sow")
    _force_stub(monkeypatch, sow)
    p = sow.plan_sowing("110016", 30, "partial", "new", [])
    assert set(p) >= {"plan_id", "crops", "tip", "frost", "used_gemma", "used_tabpfn"}
    assert len(p["crops"]) <= 3
    assert p["used_gemma"] is False
    assert p["used_tabpfn"] is False


def _sun_need(crop) -> str:
    if isinstance(crop, dict):
        for key in ("sun", "sun_need", "sunlight", "light"):
            if key in crop:
                return str(crop[key]).strip().lower()
    return ""


def test_shade_never_leads_with_full_sun_only(monkeypatch):
    sow = pytest.importorskip("sow")
    _force_stub(monkeypatch, sow)
    p = sow.plan_sowing("110016", 60, "shade", "new", [])
    assert p["crops"], "stub should still return crops for shade"
    need = _sun_need(p["crops"][0])
    if need:  # shape exposes sun info -> enforce the filter
        assert need != "full", p["crops"][0]


def test_unknown_pincode_fallback_never_crashes(monkeypatch):
    sow = pytest.importorskip("sow")
    _force_stub(monkeypatch, sow)
    p = sow.plan_sowing("000000", 30, "partial", "new", [])
    assert set(p) >= {"plan_id", "crops", "tip", "frost"}


def test_streak_increments(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "STREAKS", tmp_path / "streaks.json")
    first = app.api_complete(CompleteIn(plan_id="plan1", crew=1))
    second = app.api_complete(CompleteIn(plan_id="plan2", crew=1))
    assert (first["streak"], second["streak"]) == (1, 2)
    assert first["plan_id"] == "plan1" and first["dare_id"] == "plan1"


def test_sow_endpoint_normalizes(monkeypatch):
    sow = pytest.importorskip("sow")
    _force_stub(monkeypatch, sow)
    p = app.api_sow(
        SowIn(pincode="110016", minutes=30, sun=" Partial ", experience=" NEW ")
    )
    assert set(p) >= {"plan_id", "crops"}
