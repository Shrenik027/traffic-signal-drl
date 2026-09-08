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

METRICS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "rl", "results", "metrics.json"
)


@app.get("/api/results")
def get_results():
    """Returns the baseline-vs-agent comparison written by rl/evaluate.py."""
    if not os.path.exists(METRICS_PATH):
        raise HTTPException(
            status_code=404,
            detail="metrics.json not found -- run 'python evaluate.py' in /rl first.",
        )
    with open(METRICS_PATH) as f:
        return json.load(f)


@app.get("/")
def root():
    return {"status": "ok", "see": "/api/results"}
