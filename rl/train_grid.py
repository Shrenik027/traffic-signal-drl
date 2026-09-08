"""
STAGE C — trains the multi-agent controller for the 2x2 grid.

APPROACH: shared-policy (parameter-sharing) DQN.
One neural network controls all four junctions. At every decision point,
each junction feeds its own local observation into the same network and
gets its own action back; every junction's experience goes into the same
replay buffer. Mechanically this is done by turning sumo-rl's PettingZoo
parallel environment into a 4-slot vectorised environment (SuperSuit),
which Stable-Baselines3 then treats as four parallel copies of one
environment sharing one policy.

Why parameter sharing rather than four fully independent DQNs:
  * The four junctions are structurally identical (4-way, two phases), so
    a policy learned at one is directly meaningful at the others -- there
    is nothing to gain from four separate weight sets.
  * It quadruples the experience each gradient step learns from, which is
    what makes this trainable in minutes on a CPU rather than hours.
  * It scales: adding junctions adds experience, not parameters. Four
    independent DQNs would become forty independent DQNs on a real corridor.
  * MASTER-GUIDE.md Step 14 explicitly allows either ("independent DQN, or
    a shared policy") and warns that independent multi-agent learning is
    unstable -- parameter sharing is the stabler of the two options.

Each agent still SEES only its own junction and is rewarded only for its
own junction's traffic. Coordination is not hard-coded anywhere: if the
agents end up releasing platoons in a way that suits their neighbours, it
is because that also reduced their own queues.

Two models get trained here:
    --mode normal     shared policy on heterogeneous traffic, standard
                      observation and diff-waiting-time reward
    --mode emergency  shared policy on the elevated-ambulance-incidence
                      scenario, with the emergency-aware observation and
                      reward from emergency.py

Usage:
    python train_grid.py --mode normal    --timesteps 120000
    python train_grid.py --mode emergency --timesteps 120000
"""
import argparse
import os

os.environ.setdefault("SUMO_HOME", "/usr/share/sumo")

# --- compatibility shims -----------------------------------------------------
# sumo-rl was written against an older PettingZoo API. Two names moved in
# newer PettingZoo/SuperSuit releases. Rather than pinning outdated versions
# of three libraries, we rebind the two names sumo-rl expects. Both are
# one-line renames, not behaviour changes.
import sumo_rl.environment.env as _sumo_env  # noqa: E402
from pettingzoo.utils import AgentSelector  # noqa: E402

_sumo_env.agent_selector = AgentSelector          # class was renamed
_sumo_env.SumoEnvironmentPZ.render_mode = None    # attribute now required
# -----------------------------------------------------------------------------

import supersuit as ss  # noqa: E402
import sumo_rl  # noqa: E402
from stable_baselines3 import DQN  # noqa: E402

from emergency import EmergencyObservationFunction, emergency_reward  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(HERE, "network", "grid.net.xml")
MODELS_DIR = os.path.join(HERE, "models")
TB_DIR = os.path.join(HERE, "tensorboard")

EPISODE_SECONDS = 3000
SUMO_EXTRA = "--no-step-log --lateral-resolution 0.8"


def make_vec_env(route_file: str, emergency_aware: bool, seed="random"):
    kwargs = dict(
        net_file=NET_FILE,
        route_file=route_file,
        num_seconds=EPISODE_SECONDS,
        delta_time=5,
        yellow_time=3,
        min_green=10,
        max_green=50,
        sumo_warnings=False,
        sumo_seed=seed,
        additional_sumo_cmd=SUMO_EXTRA,
    )
    if emergency_aware:
        kwargs["observation_class"] = EmergencyObservationFunction
        kwargs["reward_fn"] = emergency_reward
    else:
        kwargs["reward_fn"] = "diff-waiting-time"

    env = sumo_rl.parallel_env(**kwargs)
    env = ss.pettingzoo_env_to_vec_env_v1(env)          # 4 junctions -> 4 slots
    env = ss.concat_vec_envs_v1(env, 1, num_cpus=1, base_class="stable_baselines3")
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["normal", "emergency"], default="normal")
    ap.add_argument("--timesteps", type=int, default=120_000)
    ap.add_argument("--model-name", type=str, default=None)
    args = ap.parse_args()

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(TB_DIR, exist_ok=True)

    emergency_aware = args.mode == "emergency"
    route_file = os.path.join(
        HERE, "network",
        "grid_emergency_train.rou.xml" if emergency_aware else "grid_normal.rou.xml",
    )
    model_name = args.model_name or (
        "grid_dqn_emergency" if emergency_aware else "grid_dqn"
    )

    env = make_vec_env(route_file, emergency_aware)

    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=1e-3,
        buffer_size=100_000,
        learning_starts=2_000,
        batch_size=128,
        gamma=0.99,
        train_freq=4,             # one gradient step per 4 env steps (4 junctions
        gradient_steps=1,         # produce experience 4x faster than a single env)
        target_update_interval=1_000,
        exploration_fraction=0.25,
        exploration_final_eps=0.02,
        verbose=1,
        tensorboard_log=TB_DIR,
    )

    print(f"[{args.mode}] training shared-policy DQN over 4 junctions "
          f"for {args.timesteps} timesteps on {os.path.basename(route_file)}")
    model.learn(total_timesteps=args.timesteps, tb_log_name=model_name)

    path = os.path.join(MODELS_DIR, model_name)
    model.save(path)
    print(f"\nSaved {path}.zip")


if __name__ == "__main__":
    main()
