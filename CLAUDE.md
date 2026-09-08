# Project: Adaptive Traffic Signal Control using Deep Reinforcement Learning

## Goal
A reinforcement-learning agent learns a traffic-signalling policy on its own and
provably beats a conventional fixed-timer controller, measured in simulation (SUMO).
Final-year major project. Built solo; must be fully explainable at the viva.

## Novelty / scope (for context, not built yet)
Base RL traffic control exists in research. The contribution is the application:
Indian heterogeneous (mixed-vehicle) traffic + emergency-vehicle priority + a
rigorous, seed-matched comparison. Current milestone is the SINGLE intersection
(mini-project). Grid + heterogeneous traffic + emergency priority come in the
major-project phase.

## Hard rules
- Free / open-source only. No paid APIs, no paid datasets, no cloud costs.
- Keep it SIMPLE. Prefer library defaults over custom cleverness until basics work.
- The ML core is the priority; the dashboard is a thin comparison layer, not the point.
- Do NOT add auth, a database, or Docker unless explicitly asked.
- After each phase, stop and confirm the exact commands and expected output.
- Do not fake results. If the agent doesn't beat the baseline, say so plainly.

## Tech stack (do not substitute without asking)
- Simulation: SUMO (system install) + TraCI, SUMO_HOME=/usr/share/sumo
- RL environment: sumo-rl (Gymnasium-compatible; SumoEnvironment, single_agent=True)
- RL algorithm: Stable-Baselines3 (DQN)
- Backend: Python + FastAPI
- Frontend: Next.js (App Router) + Recharts
- Python 3.11, TypeScript for the frontend

## Repo structure
/rl        -> SUMO networks, training + evaluation scripts, saved models, results
/backend   -> FastAPI app serving evaluation metrics as JSON
/frontend  -> Next.js dashboard (fixed-timer vs agent comparison)
/README.md -> setup + run instructions
/DEFENSE-GUIDE.md -> plain-English walkthrough of every file + likely viva questions

## Definition of "working" for this milestone
A DQN agent trained on a single 4-way intersection with asymmetric traffic achieves
LOWER average vehicle waiting time than the fixed-timer baseline when both run on
identical random seeds. The dashboard shows this comparison.

## Conventions
- Clear, commented code — every file must be explainable at the viva.
- Small, runnable steps. Each script runnable from the terminal after it's written.
- Log metrics to plain JSON so frontend and report both use them.

## Actual results achieved (update this whenever you re-run evaluate.py)
- Baseline (fixed timer) avg waiting time: 12.08s (std 0.02, seeds 42/123/2024)
- Trained agent (DQN, 60k timesteps) avg waiting time: 4.02s (std 0.08)
- Improvement: 66.7% lower average waiting time, consistent across 3 seeds
- Fairness check: heavy direction (N-S) waits ~3.3s, light direction (E-W)
  waits ~6.0s under the agent -- both far below the timer's flat 12s, and
  neither direction is starved (see DEFENSE-GUIDE.md "reward hacking check")
- Full numbers: rl/results/metrics.json
