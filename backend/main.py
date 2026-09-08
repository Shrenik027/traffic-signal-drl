"""
The whole backend, on purpose: one endpoint.

CLAUDE.md's hard rule is "no database, no auth" for this milestone -- the
dashboard just needs to read the results the RL pipeline already computed
and wrote to disk. So this app's only job is: read rl/results/metrics.json
and hand it to the frontend as JSON, with CORS open so the Next.js dev
server (a different origin/port) is allowed to fetch it.

Run:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000/api/results in a browser -- it should show
the same JSON that evaluate.py wrote.
"""
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Traffic-RL results API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for a local mini-project demo; would be locked
    allow_methods=["GET"],  # down to the actual frontend origin in production
    allow_headers=["*"],
)

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "rl", "results"
)
METRICS_PATH = os.path.join(RESULTS_DIR, "metrics.json")
GRID_METRICS_PATH = os.path.join(RESULTS_DIR, "metrics_grid.json")


def _read(path: str, produced_by: str):
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"{os.path.basename(path)} not found -- run '{produced_by}' in /rl first.",
        )
    with open(path) as f:
        return json.load(f)


@app.get("/api/results")
def get_results():
    """Mini-project: single-intersection baseline-vs-agent, from rl/evaluate.py."""
    return _read(METRICS_PATH, "python evaluate.py")


@app.get("/api/results/grid")
def get_grid_results():
    """Major project: the full 2x2 grid study, from rl/evaluate_grid.py.

    Covers all demand scenarios, the heterogeneous-traffic breakdown and the
    emergency-vehicle comparison.
    """
    return _read(GRID_METRICS_PATH, "python evaluate_grid.py")


@app.get("/")
def root():
    return {"status": "ok", "see": ["/api/results", "/api/results/grid"]}
