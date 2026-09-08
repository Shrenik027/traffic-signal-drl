# Deep Reinforcement Learning for Adaptive Traffic Signal Control under Heterogeneous Urban Traffic with Emergency-Vehicle Priority

**Author:** Shrenik — Department of Computer Engineering
**Status:** Draft. Every number in this paper comes from `rl/results/metrics_grid.json`
and `rl/results/metrics.json`, produced by `rl/evaluate_grid.py` and `rl/evaluate.py`.
Re-running those scripts regenerates every table below.

---

## Abstract

Fixed-time traffic signal control allocates green time on a schedule that is
blind to the traffic actually present, which is particularly costly on
asymmetrically loaded urban arterials. We present a deep reinforcement
learning controller for signalised intersections evaluated in the SUMO
microscopic traffic simulator, and extend it in two directions that matter
for Indian urban conditions but are largely absent from the existing
benchmark literature: (i) heterogeneous traffic composed of two-wheelers,
cars, auto-rickshaws and buses sharing lanes under a sublane lateral model,
and (ii) explicit emergency-vehicle priority learned from a reward term
rather than hard-coded pre-emption. A single shared-policy Deep Q-Network
controls a 2×2 grid of four signalised junctions from purely local
observations. Against uncoordinated fixed-time control on identical
seed-matched traffic, the learned controller reduces mean vehicle waiting
time by 65.2%, 67.1% and 73.1% at light, normal and near-saturation demand
respectively, while clearing marginally more vehicles. Adding the
emergency-aware observation and reward reduces ambulance end-to-end
clearance time by 22.1% (80.7 s → 62.8 s) and ambulance waiting time by
83.4% (16.1 s → 2.7 s), at a cost of 6.3% to ordinary traffic. An ablation
confirms the effect is attributable to the emergency reward term and not to
generic congestion relief: the same architecture trained without that term
does not improve ambulance clearance at all.

**Keywords** — traffic signal control, deep reinforcement learning, DQN,
SUMO, heterogeneous traffic, emergency vehicle priority, multi-agent

---

## I. Introduction

Urban traffic signals in most Indian cities operate on fixed-time plans:
each phase receives a pre-set green duration derived from historical
surveys and repeated regardless of present conditions. The inefficiency of
this is structural rather than incidental — a fixed plan cannot shorten a
green serving an empty approach, nor extend one serving a queue, because it
has no representation of either.

Reinforcement learning (RL) is a natural fit for this problem: signal
control is a sequential decision problem under uncertainty in which the
consequence of a decision (a queue that does or does not form) is observed
shortly afterwards and can be scored. Deep RL applied to traffic signal
control is by now an established research area, and we make no claim to
having invented the method. Our contribution is threefold and applied:

1. **A rigorous, seed-matched evaluation** across four demand regimes,
   reported with dispersion rather than as a single best run.
2. **Heterogeneous traffic modelling appropriate to Indian arterials** —
   a two-wheeler-dominated fleet with lateral filtering — where the
   discharge rate of an approach depends on the *composition* of its
   queue, not merely its length.
3. **Learned emergency-vehicle priority**, in which a green corridor
   emerges from an observation and reward design rather than from a
   hard-coded pre-emption rule, evaluated with an ablation that isolates
   its contribution.

## II. Related Work

The SUMO-RL environment of Alegre et al. provides the Gymnasium/PettingZoo
interface between SUMO and standard RL algorithms used here, and its
accompanying study of non-stationarity in RL-based signal control frames
the multi-agent difficulty we encounter. Ault and Sharon's RESCO benchmark
establishes standard scenarios and metrics for the field. Both, along with
the bulk of the deep-RL signal-control literature, evaluate on
approximately homogeneous passenger-car fleets on Western network
topologies.

Emergency-vehicle pre-emption is classically handled by rule-based systems
that force a green upon detection. Such systems are effective but
non-adaptive: they cannot trade the emergency vehicle's benefit against the
cost imposed on cross traffic, because that trade-off is not represented
anywhere in the rule. Expressing the priority as a reward term instead
places the trade-off inside the optimisation, which is the approach taken
here.

The gap this work addresses is the intersection of these: RL signal control
evaluated under *heterogeneous* traffic with *learned* emergency priority.

## III. Methodology

### A. Simulation environment

All experiments use SUMO 1.18.0 with the TraCI interface, wrapped by
SUMO-RL. Two networks are used:

- **Single intersection** (mini-project milestone): one 4-way junction,
  two-lane approaches, 200 m arms, asymmetric demand (600 veh/h/direction
  north–south against 250 veh/h/direction east–west).
- **2×2 grid** (main study): four signalised junctions at 300 m spacing,
  with eight fringe source/sink nodes. Junction spacing is short enough
  that a platoon released by one junction becomes its neighbour's arrival
  process, which is what makes the problem genuinely multi-agent.

Both networks are compiled with `netconvert`, which also generates the
fixed-time programs used as the baseline. Grid junctions use a uniform,
uncoordinated 90 s cycle — deliberately representative of common deployed
practice rather than a strawman.

### B. Heterogeneous traffic model

Vehicles are drawn per-arrival from a distribution reflecting Indian urban
arterial composition:

| Class | Share | Length (m) | Width (m) | Accel (m/s²) | Max speed (m/s) |
|---|---|---|---|---|---|
| Two-wheeler | 55% | 2.2 | 0.8 | 3.5 | 16.6 |
| Car | 25% | 4.5 | 1.8 | 2.6 | 16.6 |
| Auto-rickshaw | 13% | 3.2 | 1.4 | 2.0 | 12.5 |
| Bus | 7% | 12.0 | 2.5 | 1.2 | 11.1 |

SUMO's sublane model is enabled (lateral resolution 0.8 m) with arbitrary
lateral alignment and elevated lane-change eagerness for two-wheelers and
auto-rickshaws, permitting the lateral filtering characteristic of Indian
intersections. Consequently the number of vehicles discharged per second of
green depends on queue composition: a queue of two-wheelers clears
substantially faster than an equally long queue containing buses.

### C. RL formulation

**Observation** (per junction, all components normalised to [0,1]):
one-hot encoding of the current green phase; a flag indicating whether
minimum green has elapsed; per-lane vehicle density; per-lane queue length.
For the emergency-aware variant, two further per-lane blocks are appended:
a binary emergency-vehicle presence flag, and a proximity value rising
linearly from 0 at the 150 m detection range to 1 at the stop line.
Emergency vehicles are detected live through TraCI.

**Action**: at each decision point (every 5 s of simulated time), select
which phase should next be green. Yellow transitions of 3 s are inserted
automatically by the environment on a phase change; minimum green is 10 s
and maximum green 50 s.

**Reward**, baseline variant — the standard *diff-waiting-time* signal:

> r_t = W_{t-1} − W_t

where W_t is the total accumulated waiting time over the junction's
incoming lanes, scaled by 1/100.

**Reward**, emergency-aware variant:

> r_t = (W_{t-1} − W_t) − λ · E_t

where E_t is the summed accumulated waiting time of emergency vehicles
within detection range of the junction, scaled by 1/10, and λ = 1.0. Under
this scaling one second of ambulance delay is weighted roughly ten times a
vehicle-second of ordinary delay. This single coefficient is the mechanism
by which the priority/throughput trade-off is expressed, and Section V
reports what it costs.

### D. Learning algorithm and multi-agent structure

We use Deep Q-Networks (Stable-Baselines3, MLP policy) — appropriate
because the action space is small and discrete. Hyperparameters: learning
rate 10⁻³, replay buffer 10⁵, batch size 128, γ = 0.99, target network
update every 1000 steps, ε-greedy exploration decayed from 1.0 to 0.02 over
the first 25% of training, 100 000 timesteps (~41 episodes of 3000 s).

For the grid we adopt **parameter sharing**: one policy network is used by
all four junctions, each acting on its own local observation and receiving
its own local reward, with all four junctions' transitions written to a
shared replay buffer. This is preferred over fully independent learners
for three reasons: the junctions are structurally identical, so separate
weight sets learn redundant functions; shared experience improves sample
efficiency by a factor equal to the number of junctions; and the parameter
count is independent of network size, so the approach extends to larger
corridors. No inter-agent communication, joint action space, or centralised
critic is used — any coordination that appears is an emergent consequence of
each junction minimising its own delay.

Training used SUMO's random seeding so that each episode presents a
different traffic realisation, preventing memorisation of a single arrival
pattern. Total training time was approximately 10 minutes per model on two
CPU cores; no GPU was used.

For the emergency-aware model, training used an elevated ambulance
incidence (one per ~150 s) because at realistic incidence emergency states
occupy too small a fraction of decision steps to learn from. **All reported
results are measured at realistic incidence** (four ambulances per 50-minute
episode).

### E. Evaluation protocol

Each controller is evaluated on three random seeds per scenario. For a
given seed, all controllers face byte-identical traffic: same network, same
route file, same SUMO seed, so the same vehicles arrive at the same instants.
The only difference between runs is the signal-control logic. Actions are
taken greedily (no exploration noise). Metrics are computed from SUMO's
`tripinfo` output — per-vehicle waiting time (time below 0.1 m/s) and
end-to-end trip duration — plus per-step network queue length recorded from
the environment. We report means and standard deviations across seeds.

## IV. Results

### A. Single intersection

| Controller | Mean waiting time (s) | Vehicles cleared |
|---|---|---|
| Fixed timer | 12.08 ± 0.02 | 1400 |
| DQN agent | **4.02 ± 0.08** | 1401 |

A 66.7% reduction. Disaggregating by approach confirms the improvement is
not obtained by starving the light direction: under the agent the heavy
north–south direction waits 3.3 s and the light east–west direction 6.0 s,
both far below the timer's undifferentiated 12.1 s.

### B. Grid, heterogeneous traffic

Four signalised junctions, mixed fleet, three seeds per cell.

| Scenario | Fixed timer (s) | DQN agent (s) | Reduction | Queue: fixed → agent |
|---|---|---|---|---|
| Light | 18.69 ± 0.20 | **6.51 ± 0.16** | 65.2% | 9.3 → 2.5 |
| Normal | 20.61 ± 0.10 | **6.79 ± 0.71** | 67.1% | 20.3 → 5.3 |
| Heavy | 24.65 ± 0.14 | **6.63 ± 0.25** | 73.1% | 37.7 → 8.6 |
| Emergency | 20.76 ± 0.14 | **6.68 ± 0.65** | 67.8% | 20.4 → 5.2 |

Throughput is preserved or slightly improved in every scenario (e.g. normal
demand: 2741 → 2755 vehicles cleared), confirming that the waiting-time
reduction reflects genuinely better service rather than vehicles being
prevented from entering the network.

The margin **widens with demand** (65.2% → 73.1% from light to heavy). This
is the expected direction: a fixed plan's mis-allocation is most costly
when there is most traffic to mis-allocate, and the queue figures show the
effect clearly — at heavy demand the fixed timer sustains an average network
queue 4.4× larger than the agent's.

### C. Waiting time by vehicle class (normal demand)

| Class | Fixed timer (s) | DQN agent (s) |
|---|---|---|
| Two-wheeler | 20.32 | 6.70 |
| Car | 20.89 | 6.90 |
| Auto-rickshaw | 20.37 | 6.64 |
| Bus | 22.30 | 7.33 |

All classes improve by comparable proportions; the controller does not
achieve its aggregate result by favouring the numerically dominant
two-wheelers at the expense of buses. Buses remain the worst-served class
under both controllers, consistent with their slower discharge.

### D. Emergency-vehicle priority, with ablation

Emergency scenario, four ambulances per episode, three seeds:

| Controller | Ambulance clearance (s) | Ambulance waiting (s) | Ordinary traffic waiting (s) |
|---|---|---|---|
| Fixed timer | 80.67 ± 2.93 | 16.08 | 20.76 |
| DQN agent (no emergency term) | 83.83 ± 0.51 | 19.50 | **6.68** |
| DQN agent + emergency term | **62.83 ± 1.74** | **2.67** | 7.10 |

Three findings:

1. The emergency-aware controller clears ambulances **22.1% faster** than
   fixed-time control end-to-end, and reduces ambulance *waiting* time by
   **83.4%** (16.08 s → 2.67 s). Waiting time falling almost to zero while
   clearance time falls by a smaller proportion is the signature of the
   intended behaviour: the ambulance is no longer stopped at signals, and
   the residual journey time is travel time, which no signal policy can
   remove.

2. **The ablation is decisive.** The identical architecture trained without
   the emergency reward term does not help ambulances at all (83.83 s,
   marginally worse than fixed timing) despite reducing ordinary traffic
   delay by 67.8%. Generic congestion relief is therefore *not* sufficient
   to produce emergency priority; the improvement is attributable
   specifically to the emergency observation and reward.

3. **The trade-off is real and modest.** Emergency awareness costs ordinary
   traffic 6.3% additional waiting time (6.68 s → 7.10 s) relative to the
   emergency-agnostic agent. The emergency-aware controller still
   outperforms fixed-time control on ordinary traffic by 65.8%. We report
   this cost explicitly rather than presenting the priority behaviour as
   free.

## V. Discussion and Limitations

The consistency of the results across seeds (standard deviations under 1 s
throughout) and the widening margin with demand both support the claim that
the improvement is structural rather than incidental. The vehicle-class
breakdown and the per-approach analysis together address the standard
reward-hacking concern: no class, approach or direction is starved to
produce the aggregate number.

Limitations we state plainly:

- **Synthetic network.** The 2×2 grid is a stylised corridor, not an
  imported real junction. Importing a real local layout via OpenStreetMap
  and `osmWebWizard` is the natural next step and would test whether the
  result survives irregular geometry, dedicated turn lanes and more complex
  phase structures.
- **Stationary demand.** Each scenario holds arrival rates constant for the
  episode. Real arterials exhibit peak build-up and decay; non-stationary
  demand is a known stressor for RL controllers.
- **Simulation only.** SUMO's car-following and sublane models approximate
  Indian driving behaviour but are not calibrated against measured local
  data. Calibration against field counts would materially strengthen the
  claims.
- **Turning movements are simplified.** The single-intersection study
  models through traffic only; the grid includes turning flows but not
  protected turn phases.
- **Four junctions.** Parameter sharing is expected to scale, but this is
  argued rather than demonstrated beyond four junctions.

## VI. Conclusion

A shared-policy DQN controlling four signalised junctions from purely local
observations reduced mean vehicle waiting time by 65–73% relative to
uncoordinated fixed-time control under heterogeneous Indian traffic, with
throughput preserved and the margin widening as demand rises. Adding an
emergency-aware observation and reward term reduced ambulance clearance time
by 22.1% and ambulance waiting time by 83.4%, at a 6.3% cost to ordinary
traffic; an ablation established that this behaviour is produced by the
emergency reward term specifically and does not arise from general
congestion relief. Future work: import a real junction from OpenStreetMap,
introduce non-stationary demand profiles, calibrate the vehicle models
against local field data, and scale the shared policy to a larger corridor.

## References

*(to be completed with full citation details — these are the works the
project actually builds on)*

1. L. N. Alegre, T. Bazzan, and B. C. da Silva, "Quantifying the impact of
   non-stationarity in reinforcement learning-based traffic signal control,"
   *PeerJ Computer Science*. (SUMO-RL)
2. J. Ault and G. Sharon, "Reinforcement Learning Benchmarks for Traffic
   Signal Control," *NeurIPS Datasets and Benchmarks Track*.
3. P. A. Lopez et al., "Microscopic Traffic Simulation using SUMO,"
   *IEEE Intelligent Transportation Systems Conference (ITSC)*.
4. A. Raffin et al., "Stable-Baselines3: Reliable Reinforcement Learning
   Implementations," *Journal of Machine Learning Research*.
5. V. Mnih et al., "Human-level control through deep reinforcement
   learning," *Nature*, 2015. (DQN)
6. A recent survey on deep reinforcement learning for traffic signal
   control — search IEEE Xplore for the most current one at submission time.
7. A paper on emergency-vehicle pre-emption / priority, to position the
   contrast between rule-based pre-emption and learned priority.
