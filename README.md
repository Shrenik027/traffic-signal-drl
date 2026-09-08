# Traffic-RL — Self-Learning Adaptive Traffic Signal Control

A reinforcement-learning agent that learns to control a single traffic-signal
intersection and is measured, on identical simulated traffic, against a
conventional fixed-timer controller.

See `DEFENSE-GUIDE.md` for a plain-English walkthrough of every file, every
design decision, and likely viva questions with answers — read that before
your review.

## One-time setup

### 1. Install SUMO (the traffic simulator)

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y sumo sumo-tools sumo-doc
echo 'export SUMO_HOME=/usr/share/sumo' >> ~/.bashrc
source ~/.bashrc
```

**Windows / macOS:** see `SUMO-install-guide.md` in the project docs.

Verify:
```bash
sumo --version
echo $SUMO_HOME
```

### 2. Python environment (for `/rl`)

```bash
cd rl
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -c "import sumo_rl, stable_baselines3; print('ok')"
```

### 3. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Frontend

```bash
cd frontend
npm install
```

## Headline results

**Single intersection** — DQN vs fixed timer, 3 matched seeds:
12.08 s → **4.02 s** average waiting time (**66.7% lower**).

**2×2 grid, heterogeneous Indian traffic** — one shared policy over 4 junctions:

| Scenario | Fixed timer | RL agent | Reduction |
|---|---|---|---|
| Light | 18.69 s | 6.51 s | 65.2% |
| Normal | 20.61 s | 6.79 s | 67.1% |
| Heavy | 24.65 s | 6.63 s | 73.1% |
| Emergency | 20.76 s | 6.68 s | 67.8% |

**Emergency-vehicle priority** — ambulance clearance 80.67 s → **62.83 s**
(22.1% faster), ambulance waiting 16.08 s → **2.67 s** (83.4% lower), for a
6.3% cost to ordinary traffic. An agent trained *without* the emergency
reward term shows no ambulance improvement (83.83 s) — the ablation that
proves the effect comes from the reward design.

## Running everything, in order

```bash
cd rl && source venv/bin/activate

# ---------- MINI PROJECT: single intersection ----------
python network/build_network.py          # build the junction
python network/build_routes.py           # build the demand
python baseline.py                       # fixed-timer baseline
python train.py --timesteps 60000        # train DQN  (~9 min, CPU)
python evaluate.py --model models/dqn_traffic_v1.zip --seeds 42 123 2024

# ---------- MAJOR PROJECT: 2x2 grid ----------
python network/build_grid.py             # 4 signalised junctions
python network/build_grid_routes.py --all  # all 4 demand scenarios
python train_grid.py --mode normal    --timesteps 100000   # ~10 min
python train_grid.py --mode emergency --timesteps 100000   # ~10 min
python evaluate_grid.py --seeds 42 123 2024                # ~15 min

tensorboard --logdir tensorboard/        # optional, in a second terminal
```

Then, in two more terminals:

```bash
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000
cd frontend && npm run dev
# open http://localhost:3000
```

To watch it happen visually, any scenario can be opened in the SUMO GUI:

```bash
sumo-gui -c rl/network/grid_emergency.sumocfg
```

## Repo structure

```
/rl
  network/build_network.py       single 4-way intersection
  network/build_routes.py        asymmetric demand for it
  network/build_grid.py          2x2 grid of 4 signalised junctions
  network/build_grid_routes.py   heterogeneous Indian traffic, 4 scenarios
  baseline.py                    fixed-timer baseline (single intersection)
  train.py                       DQN, single intersection
  emergency.py                   emergency observation + reward
  train_grid.py                  shared-policy multi-agent DQN
  evaluate.py                    single-intersection comparison
  evaluate_grid.py               full multi-scenario study
/backend     FastAPI: /api/results and /api/results/grid
/frontend    Next.js dashboard (both studies, tabbed)
/paper       IEEE-style paper draft, written from the real results
CLAUDE.md            project memory for Claude Code
DEFENSE-GUIDE.md     full walkthrough + viva prep — read this
```
