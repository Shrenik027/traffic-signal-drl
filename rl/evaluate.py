"""
THE KEY RESULT SCRIPT.

Runs the fixed-timer baseline and the trained DQN agent on IDENTICAL traffic
(matched random seeds) and compares them. This is the one number your whole
mini-project stands on: does the agent produce lower average vehicle waiting
time than the fixed timer, on traffic neither controller got to "cheat" on?

Fairness, explained (know this for the viva):
  Both controllers are run through sumo-rl's *same* SumoEnvironment class,
  on the *same* network, the *same* route file, and the *same* --seed for a
  given trial (seed controls SUMO's own random vehicle-arrival draws). The
  ONLY thing that differs is which one decides the traffic light phase:
    - baseline: fixed_ts=True -> the env ignores actions and just runs the
      network's own built-in two-phase timer (netconvert's default program).
    - agent:    fixed_ts=False -> the trained DQN model's action is applied
      at every decision step.
  Everything else (vehicle physics, lane geometry, demand) is byte-for-byte
  identical between the two runs for a given seed.

We run this across MULTIPLE seeds (not just one) and report the average
improvement, because a single lucky run proves nothing -- see
MASTER-GUIDE.md Step 18 ("report spread, not just a single best number").

Usage:
    python evaluate.py --model models/dqn_traffic_v1.zip
    python evaluate.py --model models/dqn_traffic_v1.zip --seeds 42 123 2024
"""
import argparse
import json
import os
from datetime import datetime, timezone

os.environ.setdefault("SUMO_HOME", "/usr/share/sumo")

import numpy as np  # noqa: E402
import sumo_rl  # noqa: E402
from stable_baselines3 import DQN  # noqa: E402

from baseline import summarize  # reuse the tripinfo-parsing helper  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(HERE, "network", "intersection.net.xml")
ROUTE_FILE = os.path.join(HERE, "network", "intersection.rou.xml")
RESULTS_DIR = os.path.join(HERE, "results")
EPISODE_SECONDS = 3000
DELTA_TIME = 5

ENV_KWARGS = dict(
    net_file=NET_FILE,
    route_file=ROUTE_FILE,
    use_gui=False,
    num_seconds=EPISODE_SECONDS,
    delta_time=DELTA_TIME,
    yellow_time=3,
    min_green=10,
    max_green=50,
    single_agent=True,
    reward_fn="diff-waiting-time",
    sumo_warnings=False,
)


def run_episode(seed: int, fixed_ts: bool, model=None, tripinfo_path: str = None):
    """Runs one episode (fixed-timer or agent-controlled) and returns
    (per_step_metrics, tripinfo_summary)."""
    extra_cmd = "--no-step-log"
    if tripinfo_path:
        extra_cmd += f" --tripinfo-output {tripinfo_path}"

    env = sumo_rl.SumoEnvironment(
        **ENV_KWARGS,
        fixed_ts=fixed_ts,
        sumo_seed=seed,
        additional_sumo_cmd=extra_cmd,
    )
    obs, _ = env.reset(seed=seed)
    done = False
    while not done:
        if fixed_ts:
            obs, reward, terminated, truncated, info = env.step(None)
        else:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(int(action))
        done = terminated or truncated
    metrics = list(env.metrics)  # list of per-step info dicts
    env.close()

    tripinfo_summary = summarize(tripinfo_path) if tripinfo_path else None
    return metrics, tripinfo_summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=str, required=True, help="path to the trained .zip model")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 123, 2024])
    args = ap.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    model = DQN.load(args.model)

    baseline_waits, agent_waits = [], []
    baseline_cleared, agent_cleared = [], []
    timeseries = None  # per-step chart data, captured from the first seed

    for i, seed in enumerate(args.seeds):
        print(f"\n=== Seed {seed} ===")

        b_trip = os.path.join(RESULTS_DIR, f"eval_baseline_seed{seed}.xml")
        b_metrics, b_summary = run_episode(seed, fixed_ts=True, tripinfo_path=b_trip)
        print(f"  baseline: avg waiting time = {b_summary['avg_waiting_time']:.2f} s "
              f"({b_summary['vehicles_cleared']} vehicles cleared)")
        baseline_waits.append(b_summary["avg_waiting_time"])
        baseline_cleared.append(b_summary["vehicles_cleared"])

        a_trip = os.path.join(RESULTS_DIR, f"eval_agent_seed{seed}.xml")
        a_metrics, a_summary = run_episode(seed, fixed_ts=False, model=model, tripinfo_path=a_trip)
        print(f"  agent:    avg waiting time = {a_summary['avg_waiting_time']:.2f} s "
              f"({a_summary['vehicles_cleared']} vehicles cleared)")
        agent_waits.append(a_summary["avg_waiting_time"])
        agent_cleared.append(a_summary["vehicles_cleared"])

        if i == 0:
            n = min(len(b_metrics), len(a_metrics))
            timeseries = [
                {
                    "step": int(b_metrics[j]["step"]),
                    "baseline_waiting_time": round(float(b_metrics[j]["system_mean_waiting_time"]), 2),
                    "agent_waiting_time": round(float(a_metrics[j]["system_mean_waiting_time"]), 2),
                }
                for j in range(n)
            ]

    baseline_avg = float(np.mean(baseline_waits))
    agent_avg = float(np.mean(agent_waits))
    improvement_pct = (baseline_avg - agent_avg) / baseline_avg * 100

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seeds": args.seeds,
        "episode_seconds": EPISODE_SECONDS,
        "baseline": {
            "avg_waiting_time": round(baseline_avg, 2),
            "std_waiting_time": round(float(np.std(baseline_waits)), 2),
            "avg_vehicles_cleared": round(float(np.mean(baseline_cleared)), 1),
            "per_seed_waiting_time": [round(w, 2) for w in baseline_waits],
        },
        "agent": {
            "avg_waiting_time": round(agent_avg, 2),
            "std_waiting_time": round(float(np.std(agent_waits)), 2),
            "avg_vehicles_cleared": round(float(np.mean(agent_cleared)), 1),
            "per_seed_waiting_time": [round(w, 2) for w in agent_waits],
        },
        "improvement_pct": round(improvement_pct, 1),
        "timeseries": timeseries,
        "timeseries_seed": args.seeds[0],
    }

    out_path = os.path.join(RESULTS_DIR, "metrics.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print("\n" + "=" * 50)
    print(f"Baseline avg waiting time: {baseline_avg:.2f}s  (std {np.std(baseline_waits):.2f})")
    print(f"Agent    avg waiting time: {agent_avg:.2f}s  (std {np.std(agent_waits):.2f})")
    if improvement_pct > 0:
        print(f"RESULT: agent is {improvement_pct:.1f}% BETTER than the fixed timer.")
    else:
        print(f"RESULT: agent is {-improvement_pct:.1f}% WORSE than the fixed timer. "
              f"Do not report this as a win -- go back to train.py / the reward.")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
