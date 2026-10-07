"""Frost & Sow garden planner API. Run: uvicorn app:app --app-dir src"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from sow import plan_sowing  # noqa: E402
except ImportError:  # sow lane hasn't landed yet -> dares shim keeps app bootable
    from dares import deal_dare as plan_sowing  # noqa: E402

app = FastAPI()
STREAKS = Path(__file__).resolve().parent.parent / "data" / "streaks.json"


class SowIn(BaseModel):
    pincode: str
    minutes: int = Field(ge=5, le=300)
    sun: str = "partial"
    experience: str = "new"


class CompleteIn(BaseModel):
    plan_id: str
    crew: int = 1


def _load_streaks() -> dict:
    try:
        return json.loads(STREAKS.read_text())
    except Exception:
        return {"streak": 0, "total": 0, "recent": []}


def _save_streaks(data: dict) -> None:
    STREAKS.parent.mkdir(parents=True, exist_ok=True)
    STREAKS.write_text(json.dumps(data))


def recent_plan_ids() -> list:
    return _load_streaks().get("recent", [])


recent_dare_ids = recent_plan_ids  # compat alias


def record_completion(dare_id: str, crew: int) -> int:
    data = _load_streaks()
    data["streak"] = data.get("streak", 0) + 1
    data["total"] = data.get("total", 0) + 1
    recent = [r for r in data.get("recent", []) if r != dare_id] + [dare_id]
    data["recent"] = recent[-20:]
    _save_streaks(data)
    return data["streak"]


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(
        Path(__file__).resolve().parent.parent / "static" / "index.html"
    )


@app.post("/api/sow")
def api_sow(body: SowIn):
    # Never 500 on a bad pincode — sow.py handles the fallback.
    return plan_sowing(
        body.pincode,
        body.minutes,
        (body.sun or "partial").strip().lower() or "partial",
        (body.experience or "new").strip().lower() or "new",
        recent_plan_ids(),
    )


@app.post("/api/complete")
def api_complete(body: CompleteIn):
    streak = record_completion(body.plan_id, body.crew)
    return {"streak": streak, "plan_id": body.plan_id, "dare_id": body.plan_id}
