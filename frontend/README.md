# Frontend

React + three.js viewer (D1, plan.md §9 P10). Talks to `backend/api`
(FastAPI) via `/api/*`, proxied by Vite's dev server to
`http://localhost:8000` (see `vite.config.ts`).

## Run

```
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api -> :8000
```

Requires the API server running separately:

```
.venv/bin/uvicorn backend.api.main:app --reload --port 8000
```

## What it does

1. Lists sample configs (`GET /api/configs/samples` — `tests/golden/*.yaml`
   + `tests/configs/devices/*.yaml`; D17's real config library hasn't
   landed, see `backend/api/routes/configs.py`).
2. Submits a build (`POST /api/jobs`), opens a progress WebSocket
   (`/api/jobs/{id}/ws`) that streams `backend.pipeline.build_wing`'s own
   per-stage checkpoints until the job reaches `done`/`failed`.
3. Loads the exported glTF (`src/Viewer.tsx`), one three.js node per body
   named with the §5 naming contract string — the SAME string used for
   STEP, so a body toggle checkbox and a STEP body are the same identity.
4. If the build has hinge kinematics (`te_surface` enabled, `mode:
   generated`), shows a deflection slider that rigidly rotates every
   CS-side node about the true hinge axis client-side (visual only — the
   authoritative check is server-side P8, plan.md §4).

`window.__wingE2E` is a debug hook for `tests/gates/test_p10_web_e2e.py`
(Playwright) — not used by the UI itself. See its own docstring in
`src/Viewer.tsx`.
