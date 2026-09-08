"""
LIVE DEMO SCRIPT — run any stage of the project in the SUMO GUI so you can
show it moving, instead of only showing numbers on a dashboard.

This is the script to drive your presentation. Nothing here trains or
evaluates anything; it loads an already-trained model and plays one episode
on screen.

Presentation sequence that matches the story "first ordinary traffic on one
junction, then I add mixed Indian traffic and scale to a corridor":

  1. python demo.py --stage mini --controller fixed
        One junction, plain car traffic, ordinary fixed timer.
        Point at the north-south queue building while east-west sits empty.

  2. python demo.py --stage mini --controller agent
        Same junction, same traffic, the trained agent driving the light.
        The queue stops building.

  3. python demo.py --stage grid --scenario normal --controller fixed
        Four junctions, and now heterogeneous Indian traffic --
        two-wheelers filtering past cars, buses, auto-rickshaws.

  4. python demo.py --stage grid --scenario normal --controller agent
        The same corridor under the shared RL policy.

  5. python demo.py --stage grid --scenario emergency --controller agent_emergency --follow
        The finale. --follow makes the camera lock onto each ambulance as it
        appears, so the panel watches the corridor turn green ahead of it.
        Ambulances enter at t = 600, 1200, 1800 and 2400 seconds.
        Run the same command with --controller fixed first for the contrast.

Useful flags:
    --delay 120     slow playback down so it is watchable (milliseconds/step)
    --begin 550     skip ahead (e.g. to just before the first ambulance)
    --no-gui        run headless, just print the numbers
"""
import argparse
import os

os.environ.setdefault("SUMO_HOME", "/usr/share/sumo")

import sumo_rl  # noqa: E402
from stable_baselines3 import DQN  # noqa: E402

from emergency import EmergencyObservationFunction, emergency_reward  # noqa: E402
from evaluate_grid import summarize_tripinfo  # same metric as the paper  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NET = os.path.join(HERE, "network")
MODELS = os.path.join(HERE, "models")
RESULTS = os.path.join(HERE, "results")

EPISODE_SECONDS = 3000
EMERGENCY_VTYPE = "emergency"


def build_env(args, tripinfo_path):
    """Construct the environment for the requested stage/scenario/controller."""
    gui = not args.no_gui
    extra = f"--no-step-log --tripinfo-output {tripinfo_path}"

    if args.stage == "mini":
        net_file = os.path.join(NET, "intersection.net.xml")
        route_file = os.path.join(NET, "intersection.rou.xml")
        model_path = os.path.join(MODELS, "dqn_traffic_v1.zip")
        emergency_aware = False
    else:
        net_file = os.path.join(NET, "grid.net.xml")
        route_file = os.path.join(NET, f"grid_{args.scenario}.rou.xml")
        extra += " --lateral-resolution 0.8"   # sublane model: lateral filtering
        emergency_aware = args.controller == "agent_emergency"
        model_path = os.path.join(
            MODELS, "grid_dqn_emergency.zip" if emergency_aware else "grid_dqn.zip"
        )

    if gui:
        # --start plays immediately instead of waiting for the play button;
        # --delay slows it to human-watchable speed.
        extra += f" --start --delay {args.delay}"

    kwargs = dict(
        net_file=net_file,
        route_file=route_file,
        use_gui=gui,
        num_seconds=EPISODE_SECONDS,
        begin_time=args.begin,
        delta_time=5,
        yellow_time=3,
        min_green=10,
        max_green=50,
        single_agent=(args.stage == "mini"),
        sumo_seed=args.seed,
        sumo_warnings=False,
        additional_sumo_cmd=extra,
        fixed_ts=(args.controller == "fixed"),
    )
    if emergency_aware:
        kwargs["observation_class"] = EmergencyObservationFunction
        kwargs["reward_fn"] = emergency_reward
    else:
        kwargs["reward_fn"] = "diff-waiting-time"

    env = sumo_rl.SumoEnvironment(**kwargs)
    model = None if args.controller == "fixed" else DQN.load(model_path)
    return env, model


def follow_ambulance(env, currently_tracking):
    """Point the sumo-gui camera at an ambulance while one is on the network.

    Purely cosmetic, but it is what turns the emergency result into something
    a panel can watch rather than read.
    """
    try:
        for veh in env.sumo.vehicle.getIDList():
            if env.sumo.vehicle.getTypeID(veh) == EMERGENCY_VTYPE:
                if veh != currently_tracking:
                    env.sumo.gui.trackVehicle("View #0", veh)
                    env.sumo.gui.setZoom("View #0", 900)
                    print(f"  [camera] following {veh}")
                return veh
        if currently_tracking is not None:
            env.sumo.gui.trackVehicle("View #0", "")  # release the camera
    except Exception:
        pass  # no GUI, or the view is named differently -- not worth crashing a demo
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["mini", "grid"], default="grid")
    ap.add_argument("--scenario", choices=["light", "normal", "heavy", "emergency"],
                    default="normal", help="grid stage only")
    ap.add_argument("--controller", choices=["fixed", "agent", "agent_emergency"],
                    default="agent")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--delay", type=int, default=80, help="ms per step in the GUI")
    ap.add_argument("--begin", type=int, default=0, help="skip ahead to this second")
    ap.add_argument("--follow", action="store_true",
                    help="camera follows ambulances (emergency scenario)")
    ap.add_argument("--no-gui", action="store_true")
    args = ap.parse_args()

    if args.stage == "mini" and args.controller == "agent_emergency":
        raise SystemExit("The emergency-aware model is for the grid stage only.")

    os.makedirs(RESULTS, exist_ok=True)
    tag = args.stage if args.stage == "mini" else f"grid_{args.scenario}"
    tripinfo_path = os.path.join(RESULTS, f"demo_{tag}_{args.controller}.xml")

    env, model = build_env(args, tripinfo_path)
    label = {"fixed": "FIXED TIMER", "agent": "RL AGENT",
             "agent_emergency": "EMERGENCY-AWARE RL AGENT"}[args.controller]
    where = "single intersection" if args.stage == "mini" else f"2x2 grid / {args.scenario}"
    print(f"\n>>> {label}  |  {where}  |  seed {args.seed}\n")

    obs = env.reset()
    if args.stage == "mini":
        obs = obs[0] if isinstance(obs, tuple) else obs

    tracking = None
    done = False
    while not done:
        if args.controller == "fixed":
            step_out = env.step(None)
        elif args.stage == "mini":
            action, _ = model.predict(obs, deterministic=True)
            step_out = env.step(int(action))
        else:
            actions = {ts: int(model.predict(o, deterministic=True)[0]) for ts, o in obs.items()}
            step_out = env.step(actions)

        if args.stage == "mini":
            obs, _, terminated, truncated, _ = step_out
            done = terminated or truncated
        else:
            obs, _, dones, _ = step_out
            done = dones["__all__"]

        if args.follow and not args.no_gui:
            tracking = follow_ambulance(env, tracking)

    steps = env.metrics
    env.close()  # closing flushes the tripinfo file SUMO has been writing

    # Report the SAME metric the paper and the dashboard report -- average
    # waiting time per vehicle, from SUMO's tripinfo output. (Deliberately
    # not the per-step network average, which is a different and much
    # smaller number; having two different "waiting times" floating around
    # in a viva is how you get caught out.)
    print(f"\n--- {label} ---")
    if os.path.exists(tripinfo_path):
        summary = summarize_tripinfo(tripinfo_path)
        print(f"average waiting time per vehicle: {summary['avg_waiting_time']:.2f} s")
        print(f"vehicles cleared:                 {summary['vehicles_cleared']}")
        if "emergency" in summary:
            e = summary["emergency"]
            print(f"ambulances:                       {e['count']}")
            print(f"  average waiting time:           {e['avg_waiting_time']:.2f} s")
            print(f"  average clearance time:         {e['avg_clearance_time']:.2f} s")
    if steps:
        mean_queue = sum(s["system_total_stopped"] for s in steps) / len(steps)
        print(f"average vehicles stopped at once: {mean_queue:.1f}")


if __name__ == "__main__":
    main()
