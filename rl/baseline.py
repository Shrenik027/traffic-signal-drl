"""
Runs the single intersection on SUMO's DEFAULT fixed-timer signal program
(the plain two-phase program netconvert generated: NS green ~42s, then EW
green ~42s, with 3s yellow between) and reports the average vehicle waiting
time. This number is the baseline every later agent must beat.

No RL, no TraCI control loop needed here -- we just let SUMO run the network
as-is and ask it to write a "tripinfo" file, which records, for every
vehicle that completes its trip, how long it spent waiting (speed < 0.1 m/s)
during that trip. Averaging that across all vehicles gives one clean,
standard, literature-comparable number.

Usage:
    python baseline.py                # seed 42
    python baseline.py --seed 7       # a different traffic realization
"""
import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
NET_DIR = os.path.join(HERE, "network")
RESULTS_DIR = os.path.join(HERE, "results")
SUMOCFG = os.path.join(NET_DIR, "intersection.sumocfg")


def run_fixed_timer(seed: int, tripinfo_out: str, gui: bool = False) -> None:
    if not os.path.exists(SUMOCFG):
        sys.exit(
            "intersection.sumocfg not found. Run "
            "'python network/build_network.py' and "
            "'python network/build_routes.py' first."
        )
    os.makedirs(RESULTS_DIR, exist_ok=True)
    binary = "sumo-gui" if gui else "sumo"
    cmd = [
        binary,
        "-c", SUMOCFG,
        "--seed", str(seed),
        "--tripinfo-output", tripinfo_out,
        "--no-step-log", "true",
        "--duration-log.disable", "true",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def summarize(tripinfo_out: str) -> dict:
    tree = ET.parse(tripinfo_out)
    trips = tree.getroot().findall("tripinfo")
    n = len(trips)
    if n == 0:
        return {"vehicles_cleared": 0, "avg_waiting_time": 0.0, "avg_duration": 0.0}
    total_wait = sum(float(t.get("waitingTime")) for t in trips)
    total_dur = sum(float(t.get("duration")) for t in trips)
    return {
        "vehicles_cleared": n,
        "avg_waiting_time": total_wait / n,
        "avg_duration": total_dur / n,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--gui", action="store_true", help="watch it in sumo-gui instead of headless")
    args = ap.parse_args()

    tripinfo_out = os.path.join(RESULTS_DIR, f"baseline_tripinfo_seed{args.seed}.xml")
    run_fixed_timer(args.seed, tripinfo_out, gui=args.gui)
    stats = summarize(tripinfo_out)

    print("\n--- Fixed-timer baseline ---")
    print(f"Seed:              {args.seed}")
    print(f"Vehicles cleared:  {stats['vehicles_cleared']}")
    print(f"Avg waiting time:  {stats['avg_waiting_time']:.2f} s/vehicle")
    print(f"Avg trip duration: {stats['avg_duration']:.2f} s/vehicle")
    print("\nThis is the number the trained agent must beat (lower is better).")


if __name__ == "__main__":
    main()
