# Defense Guide — read this until you can explain every line without notes

This document exists for one reason: you are presenting and defending this
project **solo**, and a panel that senses you don't understand your own
code will fail you regardless of how good the result looks. Everything
below is written so you can explain the project in your own words, not
recite this file. Read it, then close it and try explaining each section
out loud to yourself.

The headline result, memorize this sentence:
> "On a single intersection with asymmetric traffic, a DQN agent trained
> from scratch reduced average vehicle waiting time by 66.7% compared to a
> conventional fixed-timer controller, tested on three different random
> traffic realizations (identical for both controllers) — 12.08s down to
> 4.02s."

---

## 1. What actually exists right now

You have a complete, working, honestly-measured mini-project:

```
rl/network/build_network.py   -> generates the road layout
rl/network/build_routes.py    -> generates the traffic demand
rl/baseline.py                -> runs the fixed-timer controller, alone
rl/train.py                   -> trains the DQN agent
rl/evaluate.py                -> the key result: agent vs baseline, matched seeds
rl/results/metrics.json       -> the real numbers evaluate.py produced
backend/main.py                -> serves metrics.json as JSON
frontend/app/page.tsx          -> the dashboard you'll demo
```

This is Stage B / the Mini-Project from MASTER-GUIDE.md, done. Stage C
(multiple intersections, real road layout, mixed Indian traffic, emergency
vehicle priority, IEEE paper) is the next phase — not started yet, and
that's fine; that's next semester's work per your own timeline.

---

## 2. The world: what SUMO is actually simulating

**File: `rl/network/build_network.py`**

Rather than fighting SUMO's `netgenerate` tool (which is built for grids
and city blocks, not a single clean crossroad), this script writes two
plain text files by hand — `intersection.nod.xml` (five points: one center,
four arms — North, South, East, West) and `intersection.edg.xml` (eight
roads: one lane pair in and one out for each arm) — and hands them to
`netconvert`, SUMO's official network compiler. `netconvert` figures out
lane connections, turn permissions, and (because we pass `--tls.guess`)
automatically writes a traffic light program at the center junction.

**Why a hand-built network instead of a downloaded/tutorial one:** so you
can honestly say "I designed this junction" — five nodes, eight edges, one
signal. If asked to draw it on a whiteboard, you can, from memory:

```
        N
        |
W ----- C ----- E
        |
        S
```

**File: `rl/network/build_routes.py`**

This writes `intersection.rou.xml` — the traffic demand. It defines one
`vType` (a generic car) and four `flow`s: North↔South traffic at 600
vehicles/hour per direction, East↔West at 250/hour per direction. That
asymmetry (roughly 2.4x) is deliberate and important to your defense: a
fixed timer gives every direction the same number of seconds of green
regardless of how many cars are actually there. On a perfectly balanced
intersection, a dumb timer already looks reasonable. On an *unbalanced*
one — like most real junctions — it wastes green time on an empty road
while the busy road backs up. That's precisely the gap an agent that can
see queue lengths should be able to close, and it's why we chose asymmetric
demand rather than a "nicer-looking" balanced one.

Only straight-through movements are modeled (no turns) — a deliberate scope
cut to keep the mini-project's moving parts countable. Turning traffic is a
natural, easy-to-name extension for the major-project phase.

**Reproducibility:** the demand rates are fixed in the file, but the exact
*second* each car appears is randomized by SUMO itself, controlled by a
`--seed` value passed at run time. Same file + same seed = identical
traffic, every time. That's what makes a fair baseline-vs-agent comparison
possible (Section 5).

---

## 3. The baseline: what "fixed timer" actually means here

**File: `rl/baseline.py`**

`netconvert --tls.guess` wrote a simple two-phase program at the center
junction: North-South green for 42 seconds, 3 seconds yellow, East-West
green for 42 seconds, 3 seconds yellow, repeat forever — deaf to whether
anyone is actually waiting. `baseline.py` just runs plain SUMO on this
program for 3000 simulated seconds (50 minutes) and asks SUMO to write a
"tripinfo" file: one record per vehicle, including how many seconds of its
trip it spent stationary (`waitingTime`). Averaging that across every
vehicle gives one clean number — **12.08 seconds average wait**, our line
in the sand.

**Why SUMO's `waitingTime` and not something home-grown:** it's a built-in,
well-defined SUMO metric (time spent below 0.1 m/s) used throughout the
traffic-simulation literature, so your result is comparable to what a
reviewer would expect, not an ad hoc measurement you invented.

---

## 4. The agent: how it sees, decides, and learns

**File: `rl/train.py`**, using the `sumo-rl` library on top of SUMO + TraCI,
and Stable-Baselines3 for the learning algorithm.

**Observation — what the agent is given every decision:**
`sumo-rl`'s default observation function returns, for the one junction:
- a one-hot vector of which phase is currently green
- whether the minimum green time has elapsed yet (can it legally switch?)
- the queue length on each incoming lane, normalized
- the accumulated waiting time on each incoming lane, normalized

In plain words: *"which light is on, how long it's been on, and how bad
each direction's queue currently is."* That's genuinely everything a human
traffic controller looking at camera feeds would use.

**Action — what the agent picks:** every 5 simulated seconds (`delta_time=5`
in `train.py`), it picks one of two things: "keep North-South green" or
"switch to East-West green." `sumo-rl` automatically inserts the 3-second
yellow transition when the agent asks to switch — the agent never has to
think about yellow lights directly, matching how real signal controllers
work (yellow is a safety interval, not a decision).

**Reward — what teaches it right from wrong:**
`reward_fn="diff-waiting-time"`, `sumo-rl`'s library default:

```
reward = (total waiting time across all lanes, last step)
        - (total waiting time across all lanes, this step)
```

If waiting time went down, reward is positive. If it went up, reward is
negative. There is no reward term for "keep a nice cycle" or "be fair" —
fairness (Section 6) is something we *checked for*, not something we
programmed in.

**Why this reward and not something hand-crafted:** CLAUDE.md's own rule is
"prefer library defaults over custom cleverness until basics work" — and
here the default worked well enough on the first real training run that no
custom reward shaping was needed. If a panelist asks "why didn't you design
your own reward function," the honest answer is: "I started from the
standard one used in the SUMO-RL literature, verified it produces a fair,
non-degenerate policy, and it already beat the baseline by a wide margin,
so more complexity wasn't justified for this milestone. Reward engineering
is exactly where I'd invest more effort for the multi-intersection /
emergency-vehicle major-project phase."

**Algorithm — DQN (Deep Q-Network):** the action space here is tiny and
discrete (2 choices), which is exactly the case DQN was designed for — it
learns a function that estimates "how good is each of my 2 choices right
now" and picks the best one. A neural network (Stable-Baselines3's default
2-layer MLP) approximates that function from the observation. PPO is the
documented fallback if DQN training were unstable — it wasn't needed here.

**Training setup (the actual hyperparameters used, in `train.py`):**
60,000 timesteps (100 episodes of 3000 simulated seconds each), learning
rate 1e-3, a replay buffer of 50,000 past experiences, batch size 64,
epsilon-greedy exploration decaying from 100% to 2% over the first 20% of
training. Training used `sumo_seed="random"` — a *different* random traffic
realization every episode — deliberately, so the agent has to learn a
general "clear the longer queue" strategy instead of memorizing one
specific traffic pattern. It took about 8-9 minutes on a standard CPU (no
GPU needed — the network is small and the simulation itself, not the
neural net, is the bottleneck).

**If asked "why 60,000 timesteps and not more/fewer":** this was long
enough to clearly beat the baseline with margin to spare, on limited
compute. More timesteps is cheap to try again (`python train.py --timesteps
150000`) — a good thing to actually do before your review, to show you
understand it's a knob you can turn, not a magic number.

---

## 5. The evaluation: what makes the comparison fair

**File: `rl/evaluate.py`** — this is the file to understand most deeply,
because "how did you make sure this is a fair comparison" is close to a
guaranteed question.

Both the baseline and the agent run through the exact same `sumo_rl.
SumoEnvironment` class, on the exact same network and route file, for the
exact same simulated duration. The **only** difference:
- baseline run: `fixed_ts=True` — the environment ignores whatever action
  you pass it and just lets the junction's own built-in timer program run.
- agent run: `fixed_ts=False` — the trained model's action is applied at
  every decision step (`model.predict(obs, deterministic=True)` — greedy,
  no exploration randomness, since we want its *best* learned behavior for
  evaluation, not exploratory noise).

Crucially, both runs for a given trial use the **same `--seed`**, so the
exact same sequence of vehicles, at the exact same simulated moments,
approaches both controllers. Neither one gets easier or harder traffic than
the other.

We do this across **three different seeds** (42, 123, 2024) — not just one
— and report the average and the spread (standard deviation), per
MASTER-GUIDE.md Step 18's rule: "report spread, not just a single best
number." The result was remarkably consistent: 12.05s / 12.10s / 12.07s for
the baseline, 4.08s / 4.07s / 3.91s for the agent, across the three seeds —
low variance, so this isn't one lucky run.

`evaluate.py` writes everything to `rl/results/metrics.json`, including a
step-by-step time series (mean waiting time every 5 seconds across the
episode) for the dashboard's chart.

---

## 6. The reward-hacking check (do this yourself before your review, too)

MASTER-GUIDE.md Step 9 explicitly warns: an agent optimizing "reduce total
waiting time" can cheat by permanently starving the low-traffic direction
to keep the high-traffic direction flowing, since that can look good in an
*aggregate* number while being unusable in practice. We checked for this
by splitting the tripinfo results by direction:

| Direction | Vehicles | Avg wait (agent) | Avg wait (fixed timer) |
|---|---|---|---|
| North-South (heavy) | 991 | 3.3s | 12.08s (all directions, timer's flat) |
| East-West (light)   | 410 | 6.0s | 12.08s |

Both directions are far better off under the agent than under the timer,
and — sensibly — the heavier direction gets slightly more favorable
treatment (more green time allocated proportionally to demand), not less.
Nobody is being starved. This is the kind of check a panel respects: you
didn't just trust the headline number, you went looking for the way it
could be fake and showed it wasn't.

Re-run this check yourself any time with:
```bash
cd rl && source venv/bin/activate
python -c "
import xml.etree.ElementTree as ET
from collections import defaultdict
t = ET.parse('results/eval_agent_seed42.xml')
by_dir = defaultdict(list)
for trip in t.getroot().findall('tripinfo'):
    by_dir[trip.get('id').split('.')[0]].append(float(trip.get('waitingTime')))
for k, v in by_dir.items():
    print(k, 'n=', len(v), 'avg_wait=', round(sum(v)/len(v), 2))
"
```

---

## 7. The dashboard: what it shows and why it's built this way

`backend/main.py` is intentionally one endpoint (`GET /api/results`) doing
one thing: reading `metrics.json` and returning it. No database — there's
nothing to store beyond a results file, so a database would be unjustified
complexity (and CLAUDE.md's hard rule says don't add one without a reason).

`frontend/app/page.tsx` fetches that JSON and renders: two summary cards
(fixed timer vs. agent, with the % improvement badge), and a line chart of
mean waiting time across the whole 50-minute episode for both controllers
overlaid. The fixed timer's line is a repeating sawtooth — queue builds for
~42 seconds, then flushes when the light turns green, again and again. The
agent's line stays low and mostly flat, occasionally spiking when a burst
of cars arrives, then recovering fast. That visual, more than the single
66.7% number, is what makes the result *legible* to a panel at a glance —
lead with it in your demo.

---

## 8. Likely viva questions, and how to answer them honestly

**"Hasn't RL traffic control already been done?"**
Yes — say so plainly, don't get defensive. "Base reinforcement-learning
traffic signal control is published research; my contribution here is
demonstrating it end-to-end on my own network with a rigorous, seed-matched
comparison, and the next phase adds a genuine application twist — Indian
heterogeneous traffic and emergency-vehicle priority — which is where the
novelty lives, not in inventing a new RL algorithm."

**"Why DQN and not a fancier algorithm?"**
"The action space is a small discrete choice — which phase to make
green — which is exactly what DQN is designed for. PPO was the planned
fallback if DQN training were unstable, but it converged cleanly, so
there was no reason to add complexity."

**"How do you know the agent didn't just get lucky?"**
Point to Section 5 — three different random seeds, low standard deviation,
consistent ~66-67% improvement on each. Not one run.

**"Why should I believe your baseline is fair — maybe you picked a bad
timer?"**
The timer program wasn't hand-picked to look weak — it's SUMO's own
automatically-generated default program from `netconvert --tls.guess`, an
ordinary two-phase 42/42-second split, which is a realistic and common
real-world fixed-timer configuration, not a strawman.

**"What happens if traffic is heavier / lighter than what you tested?"**
Honest answer: "This milestone tests one demand level. Testing across a
range of demand levels (light / moderate / heavy / oversaturated) is
exactly the kind of expanded evaluation study Stage C's Step 18 calls for,
and is planned for the major-project phase."

**"Explain this specific line of code to me."**
This is why you read this whole document and the actual `.py` files
side by side — every script above is short (under ~150 lines) and
commented specifically so you can trace any line back to the concept it
implements. If a panelist points at `reward_fn="diff-waiting-time"`,
you should be able to say the sentence in Section 4's Reward paragraph
without looking it up.

**"Why not just use ChatGPT / an LLM for this?"**
"This isn't a language problem — it's a sequential decision-making
problem under uncertainty, which is what reinforcement learning is built
for. An LLM has no way to observe live queue lengths and learn a control
policy through trial and error against a physics-based traffic simulator;
that's a fundamentally different kind of learning than next-token
prediction."

**"What's next / what's the major project?"**
Multiple cooperating intersections (a small grid, independent DQN agents
per signal), a real local road layout imported from OpenStreetMap via
SUMO's `osmWebWizard`, heterogeneous Indian traffic (two-wheelers, buses,
mixed with cars), emergency-vehicle priority (detect an approaching
ambulance via TraCI, add a reward term for clearing its path fast), a
full multi-seed, multi-scenario evaluation study, and an IEEE-style paper
from the results. See `traffic-rl-build-plan.md` Sections 7 and Master
Guide Stage C for the full roadmap.

---

## 9. Re-running everything from scratch (do this once before your review)

```bash
cd rl && source venv/bin/activate
python network/build_network.py
python network/build_routes.py
python baseline.py --seed 42
python train.py --timesteps 60000 --model-name dqn_traffic_v1
python evaluate.py --model models/dqn_traffic_v1.zip --seeds 42 123 2024
```
Then, in two more terminals:
```bash
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000
cd frontend && npm run dev
```
Open `http://localhost:3000`. If every one of these commands makes sense to
you and produces what this guide says it should, you're ready.
