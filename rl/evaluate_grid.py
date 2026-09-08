"""
STAGE C — the full evaluation study.

This is the file that produces the results table for the paper and the
viva. It compares controllers across FOUR demand scenarios, on MULTIPLE
matched random seeds each, and reports means with standard deviations --
because, per MASTER-GUIDE.md Step 18, "report spread, not just a single
best number."

Controllers compared:
    fixed            the network's own uncoordinated fixed-timer programs
                     (90 s cycle at every junction) -- what a city deploys
    agent            shared-policy DQN, standard observation/reward
    agent_emergency  shared-policy DQN with the emergency-aware observation
                     and reward from emergency.py

Scenarios:
    light / normal / heavy   heterogeneous Indian traffic at three demand
                             levels (off-peak, normal, near-saturation)
    emergency                normal demand plus four ambulances crossing
                             the corridor

The emergency scenario is run with ALL THREE controllers on purpose. That
gives an ablation, not just a demo: if 'agent' and 'agent_emergency' were
to clear ambulances equally fast, the emergency reward term would be doing
nothing and we would have to say so.

Fairness: every controller sees the same network, the same route file, and
the same SUMO --seed for a given trial, so the same vehicles arrive at the
same moments. Only the signal-control logic differs.

Usage:
    python evaluate_grid.py --seeds 42 123 2024
"""
import argparse
import json
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

os.environ.setdefault("SUMO_HOME", "/usr/share/sumo")

import numpy as np  # noqa: E402
import sumo_rl  # noqa: E402
from stable_baselines3 import DQN  # noqa: E402

from emergency import EmergencyObservationFunction, emergency_reward  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(HERE, "network", "grid.net.xml")
RESULTS_DIR = os.path.join(HERE, "results")
MODELS_DIR = os.path.join(HERE, "models")

EPISODE_SECONDS = 3000
SCENARIOS = ["light", "normal", "heavy", "emergency"]


def route_file(scenario: str) -> str:
    return os.path.join(HERE, "network", f"grid_{scenario}.rou.xml")


def run_episode(scenario: str, seed: int, controller: str, model=None, tripinfo_path=None):
    """Run one full episode under one controller. Returns (per_step_metrics, tripinfo_summary)."""
    extra = "--no-step-log --lateral-resolution 0.8"
    if tripinfo_path:
        extra += f" --tripinfo-output {tripinfo_path}"

    kwargs = dict(
        net_file=NET_FILE,
        route_file=route_file(scenario),
        num_seconds=EPISODE_SECONDS,
        delta_time=5,
        yellow_time=3,
        min_green=10,
        max_green=50,
        single_agent=False,
        sumo_warnings=False,
        sumo_seed=seed,
        additional_sumo_cmd=extra,
        fixed_ts=(controller == "fixed"),
    )
    # The observation space must match whatever the model was trained on.
    if controller == "agent_emergency":
        kwargs["observation_class"] = EmergencyObservationFunction
        kwargs["reward_fn"] = emergency_reward
    else:
        kwargs["reward_fn"] = "diff-waiting-time"

    env = sumo_rl.SumoEnvironment(**kwargs)
    obs = env.reset()
    done = False
    while not done:
        if controller == "fixed":
            obs, rewards, dones, info = env.step(None)
        else:
            actions = {ts: int(model.predict(o, deterministic=True)[0]) for ts, o in obs.items()}
            obs, rewards, dones, info = env.step(actions)
        done = dones["__all__"]

    metrics = list(env.metrics)
    env.close()
    return metrics, (summarize_tripinfo(tripinfo_path) if tripinfo_path else None)


def summarize_tripinfo(path: str) -> dict:
    """Per-vehicle statistics, overall and split by vehicle class."""
    trips = ET.parse(path).getroot().findall("tripinfo")
    if not trips:
        return {}

    by_type = defaultdict(list)
    waits, durations = [], []
    emerg_wait, emerg_dur = [], []

    for t in trips:
        w = float(t.get("waitingTime"))
        d = float(t.get("duration"))
        vtype = t.get("vType") or ""
        waits.append(w)
        durations.append(d)
        by_type[vtype].append(w)
        if vtype.startswith("emergency"):
            emerg_wait.append(w)
            emerg_dur.append(d)

    out = {
        "vehicles_cleared": len(trips),
        "avg_waiting_time": float(np.mean(waits)),
        "avg_duration": float(np.mean(durations)),
        "by_vehicle_type": {k: round(float(np.mean(v)), 2) for k, v in sorted(by_type.items())},
    }
    if emerg_wait:
        out["emergency"] = {
            "count": len(emerg_wait),
            "avg_waiting_time": float(np.mean(emerg_wait)),
            "avg_clearance_time": float(np.mean(emerg_dur)),
        }
    return out


def aggregate(runs: list) -> dict:
    """Mean/std across seeds for one (scenario, controller) cell."""
    waits = [r["avg_waiting_time"] for r in runs]
    cleared = [r["vehicles_cleared"] for r in runs]
    queues = [r["avg_queue"] for r in runs]
    cell = {
        "avg_waiting_time": round(float(np.mean(waits)), 2),
        "std_waiting_time": round(float(np.std(waits)), 2),
        "avg_vehicles_cleared": round(float(np.mean(cleared)), 1),
        "avg_queue_length": round(float(np.mean(queues)), 2),
        "per_seed_waiting_time": [round(w, 2) for w in waits],
    }
    # average the per-vehicle-type breakdown across seeds
    types = defaultdict(list)
    for r in runs:
        for k, v in r.get("by_vehicle_type", {}).items():
            types[k].append(v)
    if types:
        cell["by_vehicle_type"] = {k: round(float(np.mean(v)), 2) for k, v in sorted(types.items())}
    # emergency stats, if this scenario had ambulances
    em_wait = [r["emergency"]["avg_waiting_time"] for r in runs if "emergency" in r]
    em_clear = [r["emergency"]["avg_clearance_time"] for r in runs if "emergency" in r]
    if em_wait:
        cell["emergency"] = {
            "avg_waiting_time": round(float(np.mean(em_wait)), 2),
            "avg_clearance_time": round(float(np.mean(em_clear)), 2),
            "std_clearance_time": round(float(np.std(em_clear)), 2),
        }
    return cell


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 123, 2024])
    ap.add_argument("--model", default=os.path.join(MODELS_DIR, "grid_dqn.zip"))
    ap.add_argument("--emergency-model", default=os.path.join(MODELS_DIR, "grid_dqn_emergency.zip"))
    args = ap.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    model = DQN.load(args.model)
    model_em = DQN.load(args.emergency_model)

    results = {}
    timeseries = None

    for scenario in SCENARIOS:
        controllers = ["fixed", "agent"]
        if scenario == "emergency":
            controllers.append("agent_emergency")

        results[scenario] = {}
        for controller in controllers:
            runs = []
            per_step_first = None
            for seed in args.seeds:
                tp = os.path.join(RESULTS_DIR, f"grid_{scenario}_{controller}_s{seed}.xml")
                m = model_em if controller == "agent_emergency" else model
                steps, summary = run_episode(scenario, seed, controller, model=m, tripinfo_path=tp)
                summary["avg_queue"] = float(np.mean([s["system_total_stopped"] for s in steps]))
                runs.append(summary)
                if per_step_first is None:
                    per_step_first = steps
                print(f"  {scenario:10s} {controller:16s} seed {seed:5d}  "
                      f"wait={summary['avg_waiting_time']:6.2f}s  "
                      f"cleared={summary['vehicles_cleared']:5d}  "
                      f"queue={summary['avg_queue']:6.1f}"
                      + (f"  ambulance={summary['emergency']['avg_clearance_time']:.1f}s"
                         if "emergency" in summary else ""))
            results[scenario][controller] = aggregate(runs)

            # keep the normal-scenario per-step traces for the dashboard chart
            if scenario == "normal" and controller in ("fixed", "agent"):
                if timeseries is None:
                    timeseries = {}
                timeseries[controller] = [
                    {"step": int(s["step"]), "wait": round(float(s["system_mean_waiting_time"]), 2)}
                    for s in per_step_first
                ]

        # headline improvement per scenario
        f = results[scenario]["fixed"]["avg_waiting_time"]
        a = results[scenario]["agent"]["avg_waiting_time"]
        results[scenario]["improvement_pct"] = round((f - a) / f * 100, 1)

    # emergency-specific headline: how much faster does an ambulance clear?
    em = results["emergency"]
    if "emergency" in em["fixed"] and "emergency" in em["agent_emergency"]:
        f_clear = em["fixed"]["emergency"]["avg_clearance_time"]
        a_clear = em["agent_emergency"]["emergency"]["avg_clearance_time"]
        em["emergency_improvement_pct"] = round((f_clear - a_clear) / f_clear * 100, 1)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seeds": args.seeds,
        "episode_seconds": EPISODE_SECONDS,
        "network": "2x2 grid, 4 signalised junctions",
        "traffic": "heterogeneous (55% two-wheeler / 25% car / 13% auto / 7% bus)",
        "scenarios": results,
        "timeseries": timeseries,
    }
    out = os.path.join(RESULTS_DIR, "metrics_grid.json")
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=2)

    print("\n" + "=" * 72)
    print(f"{'scenario':12s} {'fixed':>10s} {'agent':>10s} {'improvement':>13s}")
    for sc in SCENARIOS:
        r = results[sc]
        print(f"{sc:12s} {r['fixed']['avg_waiting_time']:9.2f}s "
              f"{r['agent']['avg_waiting_time']:9.2f}s {r['improvement_pct']:12.1f}%")
    if "emergency_improvement_pct" in em:
        print(f"\nAmbulance clearance time: "
              f"fixed {em['fixed']['emergency']['avg_clearance_time']:.1f}s -> "
              f"emergency-aware agent {em['agent_emergency']['emergency']['avg_clearance_time']:.1f}s "
              f"({em['emergency_improvement_pct']}% faster)")
        print(f"  (base agent, no emergency reward: "
              f"{em['agent']['emergency']['avg_clearance_time']:.1f}s)")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
