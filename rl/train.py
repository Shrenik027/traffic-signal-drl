"""
Trains a DQN agent (Stable-Baselines3) to control the single intersection's
traffic light, using sumo-rl's Gymnasium-compatible SumoEnvironment.

How the pieces fit together (know this cold for the viva):

  Observation (what the agent sees each decision step):
      sumo-rl's DefaultObservationFunction returns, per intersection:
      [one-hot current phase] + [phase min-green-elapsed flag]
      + [normalized queue length per lane] + [normalized waiting time per lane]

  Action (what the agent picks each decision step, every `delta_time` seconds):
      an integer choosing which signal phase should be green next.
      sumo-rl inserts the correct yellow transition automatically when the
      phase changes -- the agent never "sees" or picks yellow directly.

  Reward (what shapes learning), reward_fn="diff-waiting-time" (the library
  default, deliberately NOT hand-tuned here first -- see CLAUDE.md rule
  "prefer library defaults until basics work"):
      reward = (total waiting time last step) - (total waiting time this step)
      i.e. the agent is rewarded for REDUCING total waiting time, and
      punished for letting it grow. This is exactly what we're measuring
      in evaluate.py, so agent and metric are aligned by construction.

  Algorithm: DQN (Deep Q-Network) -- appropriate because the action space
  here is small and discrete (pick one of a handful of phases), which is
  exactly what DQN is built for. PPO is the documented fallback if DQN
  training is unstable (see CLAUDE.md / MASTER-GUIDE Step 9).

sumo_seed="random": each training episode gets a DIFFERENT random traffic
realization (not the fixed seed used for evaluation). This matters -- if we
trained on one fixed seed, the agent could memorise that one traffic
pattern instead of learning a general queue-clearing policy. Evaluation
(evaluate.py) then tests on specific held-out seeds the agent has not seen
mapped to a memorised solution for.

Usage:
    python train.py                      # default: 50,000 timesteps
    python train.py --timesteps 150000   # longer run for a better policy
    tensorboard --logdir tensorboard/    # watch the reward curve, separately
"""
import argparse
import os

from sumo_home import ensure_sumo_home  # noqa: E402

ensure_sumo_home()  # locate SUMO on this machine before sumo_rl is imported

import sumo_rl  # noqa: E402
from stable_baselines3 import DQN  # noqa: E402
from stable_baselines3.common.monitor import Monitor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(HERE, "network", "intersection.net.xml")
ROUTE_FILE = os.path.join(HERE, "network", "intersection.rou.xml")
MODELS_DIR = os.path.join(HERE, "models")
TB_DIR = os.path.join(HERE, "tensorboard")

EPISODE_SECONDS = 3000  # keep in sync with network/build_routes.py


def make_env():
    env = sumo_rl.SumoEnvironment(
        net_file=NET_FILE,
        route_file=ROUTE_FILE,
        use_gui=False,
        num_seconds=EPISODE_SECONDS,
        delta_time=5,          # agent makes a decision every 5 simulated seconds
        yellow_time=3,         # matches the network's own yellow phase length
        min_green=10,          # can't flip-flop faster than this (realism)
        max_green=50,
        single_agent=True,     # exactly one traffic light in this milestone
        reward_fn="diff-waiting-time",
        sumo_seed="random",    # vary traffic across training episodes
        sumo_warnings=False,
        additional_sumo_cmd="--no-step-log",  # quiet the per-step console spam
    )
    return Monitor(env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=50_000)
    ap.add_argument("--model-name", type=str, default="dqn_traffic")
    args = ap.parse_args()

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(TB_DIR, exist_ok=True)

    env = make_env()

    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=1e-3,
        buffer_size=50_000,
        learning_starts=1_000,
        batch_size=64,
        gamma=0.99,
        train_freq=1,
        target_update_interval=500,
        exploration_fraction=0.2,   # % of training spent decaying epsilon
        exploration_final_eps=0.02,
        verbose=1,
        tensorboard_log=TB_DIR,
    )

    print(f"Training DQN for {args.timesteps} timesteps "
          f"({args.timesteps * 5 / EPISODE_SECONDS:.1f} episodes worth of decisions)...")
    model.learn(total_timesteps=args.timesteps, tb_log_name=args.model_name)

    model_path = os.path.join(MODELS_DIR, args.model_name)
    model.save(model_path)
    print(f"\nSaved model to {model_path}.zip")
    print(f"Watch the training curve with: tensorboard --logdir {TB_DIR}")
    print("A healthy run: the 'rollout/ep_rew_mean' curve trends UP over "
          "time (less negative / more positive), even if it's noisy.")


if __name__ == "__main__":
    main()
