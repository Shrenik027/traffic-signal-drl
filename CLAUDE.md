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

## Status: BOTH milestones built

### Mini project (single intersection) -- done
- Fixed timer 12.08s +- 0.02 -> DQN agent 4.02s +- 0.08 = 66.7% better
  (seeds 42/123/2024). Fairness check: N-S 3.3s, E-W 6.0s, neither starved.
- Full numbers: rl/results/metrics.json

### Major project (2x2 grid, heterogeneous traffic, emergency priority) -- done
- Shared-policy DQN over 4 junctions, Indian mixed fleet (55% two-wheeler /
  25% car / 13% auto / 7% bus) with SUMO sublane model for lateral filtering.
- Waiting time vs fixed timing: light 65.2%, normal 67.1%, heavy 73.1%,
  emergency 67.8% lower. Throughput preserved or slightly up in all cases.
- Emergency-aware agent: ambulance clearance 80.67s -> 62.83s (22.1% faster),
  ambulance waiting 16.08s -> 2.67s (83.4% lower), costing ordinary traffic
  6.3% more waiting (6.68s -> 7.10s).
- ABLATION: base agent without the emergency reward term gives NO ambulance
  improvement (83.83s). The priority behaviour comes from the reward term.
- Full numbers: rl/results/metrics_grid.json | Paper draft: paper/PAPER.md

## Extended scope now built (was "for context, not to build yet")
Multi-junction grid, heterogeneous Indian traffic and emergency-vehicle
priority are IMPLEMENTED. Remaining from the original roadmap: importing a
real local junction from OpenStreetMap, non-stationary demand profiles, and
calibration against local field data.
