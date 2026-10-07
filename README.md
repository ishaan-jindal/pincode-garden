# Pincode Garden (Touch Grass garden planner)

Hacktoberfest DEV challenge. Enter pincode + minutes/week + sun + experience
→ get up to 3 crops to plant, grounded in frost dates, read the tip aloud,
sow it, log the streak.

## Quickstart

Requires Python ≥ 3.12.

```sh
uv sync
uv run uvicorn app:app --app-dir src --reload
# open http://127.0.0.1:8000
```

Or without uv: `pip install -e .` then `python -m uvicorn app:app --app-dir src`.

For the real brain, pull Gemma 4 and leave Ollama running:

```sh
ollama run gemma4:e2b
```

For real TabPFN ranking locally:

```sh
uv sync --extra tabpfn
```

No API keys, no DB, no auth. Without Ollama/TabPFN, the app serves a
deterministic stub plan; with them, tip comes from Gemma and ranking from TabPFN.

> Deployed Render free runs deterministic fallback (no torch budget);
> `uv sync --extra tabpfn` enables real TabPFN locally.

## How Gemma 4 is used

`sow_plan()` is the Gemma 4 tool (lazy imports — app boots
with only fastapi+uvicorn installed):

- Frost lookup reads `data/frost.csv` (IMD/USDA normals hardcoded per
  pincode prefix) → last/first frost + weeks left.
- TabPFN V2 (cpu) ranks candidate crops by minutes/sun/experience fit;
  any failure (no torch, no tabpfn installed) falls back to a deterministic
  stdlib stub with the same return shape, so ranking never 500s.
- Gemma 4 via Ollama HTTP (`$OLLAMA_HOST`, model `$GEMMA_MODEL`, default
  `gemma4:e2b`) writes ONE short tip grounded in the ranked crops, replying
  with strict JSON; any failure (no Ollama, no model, bad JSON) falls back
  to a deterministic stub tip.
- Response carries `used_gemma` / `used_tabpfn` flags so the UI shows which
  path ran.

Offline / $0 / privacy essay hook: the whole brain runs on-device through
Ollama + local TabPFN — no cloud calls, no keys, no per-token bill, no home
gardener data leaving the LAN. The stub path means the demo works on a
conference-hall laptop with the Wi-Fi off; Gemma just makes the tips warmer
when it's home.

## API

| Route | Notes |
|---|---|
| `GET /health` | Uptime probe (Render healthcheck) |
| `GET /` | Single-page garden planner (pincode + minutes + sun → crop card + voice) |
| `POST /api/sow` | `{pincode, minutes, sun, experience}` → `{plan_id, crops[{name, why, sow_by, score}], tip, frost{last, first, weeks_left}, used_gemma, used_tabpfn}` |
| `POST /api/complete` | `{plan_id}` → `{streak, plan_id}` (streak file only) |

## Planting notes

- Frost dates are normals, not forecasts — a late cold snap can still nip seedlings.
- Sun matters: full ≥6h, partial 3–6h, shade <3h; don't force sun-lovers into shade.
- Start small: 30 min/week suits herbs/greens; squash/pumpkin want space + time.
- Water/transplant gently; if frost threatens, cover or bring pots in.

## Tests / deploy

```sh
python -m pytest -q
python src/sow.py  # stub self-check
```

Docker → Render (`Dockerfile`, `render.yaml`).

## License

MIT — see [LICENSE](LICENSE).
