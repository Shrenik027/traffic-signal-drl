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

## Running everything, in order

```bash
# 1. Generate the SUMO network + routes (only needs to be run once, or after changing demand)
cd rl && source venv/bin/activate
python network/build_network.py

# 2. Run the fixed-timer baseline
python baseline.py

# 3. Train the DQN agent (watch the curve with TensorBoard)
python train.py
tensorboard --logdir tensorboard/          # in a second terminal

# 4. Evaluate agent vs baseline on matched seeds -> rl/results/metrics.json
python evaluate.py

# 5. Start the backend (serves metrics.json as JSON)
cd ../backend && source venv/bin/activate
uvicorn main:app --reload --port 8000

# 6. Start the dashboard
cd ../frontend
npm run dev
# open http://localhost:3000
```

## Repo structure

```
/rl          SUMO network, baseline, training, evaluation, results
/backend     FastAPI app serving /api/results
/frontend    Next.js dashboard (fixed timer vs agent)
CLAUDE.md    project memory for Claude Code
DEFENSE-GUIDE.md   walkthrough + viva prep
```
