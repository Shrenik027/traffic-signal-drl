# Demo cheat sheet — keep this open during the presentation

## Done once, already finished. Never repeat:
installing SUMO · creating the venv · `pip install` · `npm install`
building the networks · training the models · running the evaluation

The trained models are in `rl/models/`. The results are in `rl/results/`.
**Nothing needs to be trained or rebuilt again.**

---

## Every time you open a NEW terminal window (2 lines)

**Windows PowerShell:**
```powershell
cd C:\Users\shren\Downloads\traffic-rl-complete\traffic-rl\rl
venv\Scripts\activate
```

**macOS / Linux:**
```bash
cd traffic-rl/rl
source venv/bin/activate
```

You'll see `(venv)` at the start of your prompt. Same terminal = don't repeat.

> ### ⚠ The trap that will bite you
> There are **three** separate virtual environments — `rl/venv`,
> `backend/venv`, `frontend` (npm). All three are literally named `venv`, so
> PowerShell shows the same `(venv)` prompt for all of them and you cannot
> tell which one is active.
>
> If you activate the backend one and then `cd rl` and run `demo.py`, you get
> **`ModuleNotFoundError: No module named 'sumo_rl'`** — the code is fine,
> you're just in the wrong environment.
>
> **Fix: use one dedicated terminal window per folder and never switch.**
> Window 1 = `rl`. Window 2 = `backend`. Window 3 = `frontend`.
>
> Also note: PowerShell does **not** support `&&`. Run each command on its
> own line.

---

## THE DEMO — six commands, in this order

### Part 1 · Mini project: one junction, ordinary car traffic

```bash
python demo.py --stage mini --controller fixed --delay 120
```
> "This is a normal traffic light — a fixed timer. Watch the north–south
> queue build up while the east–west road sits almost empty. The timer
> can't tell the difference; it gives both the same green."

```bash
python demo.py --stage mini --controller agent --delay 120
```
> "Same junction. Same traffic, same random seed — identical cars arriving
> at identical times. The only thing I changed is that a trained agent is
> now choosing the phases. The queue stops building."

**Numbers it prints:** 12.05s → 4.08s average waiting time per vehicle.

---

### Part 2 · Major project: four junctions + heterogeneous Indian traffic

```bash
python demo.py --stage grid --scenario normal --controller fixed --delay 120
```
> "Now I scale up. Four signalised junctions, and this is no longer a
> uniform stream of cars — it's 55% two-wheelers, 25% cars, 13%
> auto-rickshaws, 7% buses, and the two-wheelers filter through gaps beside
> the stopped cars. These are still ordinary fixed timers."

```bash
python demo.py --stage grid --scenario normal --controller agent --delay 120
```
> "One shared policy now controls all four junctions. Each one sees only
> its own queues — they don't communicate at all."

**Numbers it prints:** 20.49s → 5.81s average waiting time per vehicle.

---

### Part 3 · The finale: emergency vehicle

```bash
python demo.py --stage grid --scenario emergency --controller fixed --follow --begin 550 --delay 120
```
> "Same corridor, but now ambulances. The camera follows the ambulance.
> Under the fixed timer it stops and waits at red lights like everything else."

```bash
python demo.py --stage grid --scenario emergency --controller agent_emergency --follow --begin 550 --delay 120
```
> "Same ambulance, same traffic. The agent can now see it approaching and
> is penalised for delaying it — so it opens a corridor. Nothing about this
> is hard-coded; there's no pre-emption rule anywhere in my code."

**Numbers it prints:** ambulance clearance 84.75s → 65.00s, ambulance
waiting 16.50s → 4.75s.

**The killer line — say this one:**
> "And here's the control. This is the *same* agent trained *without* the
> emergency reward — it cuts ordinary traffic delay by 68%, but does
> nothing for the ambulance: 84.5 seconds, no better than the timer. So the
> improvement comes from the reward design specifically, not from just
> having less congestion."
```bash
python demo.py --stage grid --scenario emergency --controller agent --follow --begin 550 --delay 120
```

---

## The dashboard (optional — needs 2 more terminal windows)

**Terminal 2:**
```bash
cd traffic-rl/backend
source venv/bin/activate          # Windows: venv\Scripts\activate
uvicorn main:app --port 8000
```

**Terminal 3:**
```bash
cd traffic-rl/frontend
npm run dev
```

Open **http://localhost:3000**. It has two tabs — start on *Single
intersection*, switch to *Grid study* when you get to Part 2. Leave both
terminals running for the whole presentation.

---

## Flags you might want mid-demo

| Flag | What it does |
|---|---|
| `--delay 200` | slower playback (bigger = slower) |
| `--delay 20` | fast, if you're running out of time |
| `--begin 550` | skip ahead to just before the first ambulance |
| `--no-gui` | no window, just print the numbers |

Ambulances enter at t = 600, 1200, 1800 and 2400 seconds.
Close the SUMO window to end a run early and get your prompt back.

---

## If something breaks

**`ModuleNotFoundError` / `command not found: python`**
You forgot to activate the venv. Run the two lines at the top.

**`Please declare the environment variable 'SUMO_HOME'`**
The scripts now find SUMO automatically (`sumo_home.py`). If it still fails,
SUMO isn't installed or isn't on PATH — check `sumo --version` works first,
then set it manually and open a **new** terminal:
```powershell
setx SUMO_HOME "C:\Program Files (x86)\Eclipse\Sumo"
```

**A wall of `Could not connect to TraCI server ... Retrying with different port`**
That means SUMO started and immediately quit. Scroll UP past the retry spam —
the real error is above it. The usual cause was a duplicated `--start` option,
fixed in the current `demo.py`; if you see this again, run the same command
with `--no-gui` to get a readable error.

**GUI window doesn't appear**
Confirm `sumo-gui` opens on its own first. On macOS this needs XQuartz.

**Nothing at localhost:3000**
The backend (terminal 2) must be running before the page will load data.
