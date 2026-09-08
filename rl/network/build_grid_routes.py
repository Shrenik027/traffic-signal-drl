"""
STAGE C — builds the demand file for the 2x2 grid, with HETEROGENEOUS
INDIAN TRAFFIC: a realistic mix of two-wheelers, cars, auto-rickshaws and
buses sharing the same lanes, plus (in the emergency scenario) ambulances.

This is novelty part one of the major project, and it is a real modelling
choice, not cosmetic re-labelling. Three things make this "Indian mixed
traffic" rather than "cars with different lengths":

 1. COMPOSITION. Roughly 55% two-wheelers / 25% cars / 13% auto-rickshaws /
    7% buses, drawn per-vehicle from a SUMO vTypeDistribution. Western
    traffic-signal RL papers almost always assume a near-homogeneous car
    fleet; Indian arterials are two-wheeler dominated, and that changes the
    control problem because the vehicles differ hugely in how fast they
    clear a stop line.

 2. DISCHARGE HETEROGENEITY. A two-wheeler is 2.2 m long and accelerates at
    3.5 m/s^2; a bus is 12 m long and accelerates at 1.2 m/s^2. So "how
    many vehicles clear on a green" depends on WHAT is queued, not just how
    many -- the exact thing a fixed timer cannot know and a queue-observing
    agent can exploit.

 3. LATERAL FILTERING. We run SUMO's sublane model (lateral-resolution set
    in the .sumocfg), and give narrow vehicles arbitrary lateral alignment
    with high lane-change eagerness. That lets two-wheelers filter through
    gaps beside stopped cars and pack the front of the queue, which is the
    single most visually characteristic behaviour of Indian intersections
    and materially changes discharge dynamics.

Scenarios (for the evaluation study in evaluate_grid.py):
    light      -- off-peak demand
    normal     -- the default operating point
    heavy      -- near-saturation peak-hour demand
    emergency  -- normal demand plus ambulances crossing the corridor

Run:
    python network/build_grid_routes.py --scenario normal
"""
import argparse
import os

HERE = os.path.dirname(os.path.abspath(__file__))

EPISODE_SECONDS = 3000

# ---------------------------------------------------------------------------
# Vehicle fleet. Values are physically reasonable for each class; the point
# is the SPREAD between them (length, acceleration, top speed, width).
# ---------------------------------------------------------------------------
VTYPES = """
    <vTypeDistribution id="indian_mix">
        <!-- two-wheeler: short, quick, narrow, filters through gaps -->
        <vType id="motorcycle" probability="0.55" vClass="motorcycle"
               length="2.2" width="0.8" accel="3.5" decel="6.0" sigma="0.7"
               maxSpeed="16.6" minGap="1.0" latAlignment="arbitrary"
               lcSublane="5.0" lcPushy="0.8" lcAssertive="2.0" impatience="0.8"
               guiShape="motorcycle" color="1,0.6,0"/>
        <!-- passenger car -->
        <vType id="car" probability="0.25" vClass="passenger"
               length="4.5" width="1.8" accel="2.6" decel="4.5" sigma="0.5"
               maxSpeed="16.6" minGap="2.0" latAlignment="center"
               guiShape="passenger" color="0.4,0.6,1"/>
        <!-- auto-rickshaw: narrow, slow, assertive -->
        <vType id="auto" probability="0.13" vClass="taxi"
               length="3.2" width="1.4" accel="2.0" decel="4.0" sigma="0.6"
               maxSpeed="12.5" minGap="1.5" latAlignment="arbitrary"
               lcSublane="3.0" lcPushy="0.6" impatience="0.6"
               guiShape="passenger/hatchback" color="0.1,0.8,0.3"/>
        <!-- city bus: long, slow to clear a stop line -->
        <vType id="bus" probability="0.07" vClass="bus"
               length="12.0" width="2.5" accel="1.2" decel="3.5" sigma="0.4"
               maxSpeed="11.1" minGap="3.0" latAlignment="center"
               guiShape="bus" color="0.9,0.2,0.2"/>
    </vTypeDistribution>

    <!-- ambulance: allowed to use the emergency vClass, pushes through gaps,
         and is what the agent must learn to clear a corridor for -->
    <vType id="emergency" vClass="emergency" length="6.5" width="2.0"
           accel="2.8" decel="5.0" sigma="0.3" maxSpeed="22.2" minGap="2.0"
           speedFactor="1.3" guiShape="emergency" color="1,1,1"
           jmIgnoreFoeProb="0.3" jmIgnoreFoeSpeed="3.0"/>
"""

# ---------------------------------------------------------------------------
# Routes through the grid.
#   through-traffic: enters one fringe, crosses two junctions, exits opposite
#   turning traffic: enters one fringe, turns inside the grid, exits a side
# ---------------------------------------------------------------------------
ROUTES = {
    # North <-> South, both columns (the heavy arterial direction)
    "ns_left":  "N1A1 A1B1 B1S1",
    "ns_right": "N2A2 A2B2 B2S2",
    "sn_left":  "S1B1 B1A1 A1N1",
    "sn_right": "S2B2 B2A2 A2N2",
    # West <-> East, both rows (the lighter cross direction)
    "we_top":    "W1A1 A1A2 A2E1",
    "we_bottom": "W2B1 B1B2 B2E2",
    "ew_top":    "E1A2 A2A1 A1W1",
    "ew_bottom": "E2B2 B2B1 B1W2",
    # turning movements -- these are what couple the junctions together
    "turn_w_to_s": "W1A1 A1B1 B1S1",
    "turn_n_to_e": "N1A1 A1A2 A2E1",
    "turn_e_to_s": "E1A2 A2B2 B2S2",
    "turn_s_to_w": "S2B2 B2B1 B1W2",
}

# vehicles/hour per flow, per scenario
DEMAND = {
    "light":     {"ns": 250, "ew": 120, "turn": 50},
    "normal":    {"ns": 500, "ew": 250, "turn": 100},
    "heavy":     {"ns": 800, "ew": 400, "turn": 160},
    "emergency": {"ns": 500, "ew": 250, "turn": 100},
    # training-only variant: same traffic as "emergency" but with ambulances
    # arriving far more often. Rationale: at a realistic incidence (4 per
    # 50 minutes) an ambulance is present for well under 5% of decision
    # steps, which is too sparse for the agent to learn a response to. We
    # therefore TRAIN at elevated incidence to give it enough exposure, and
    # EVALUATE at the realistic incidence in the "emergency" scenario. This
    # is a curriculum choice, not a measurement trick -- the reported
    # numbers all come from the realistic scenario.
    "emergency_train": {"ns": 500, "ew": 250, "turn": 100},
}

# ambulance injection times (seconds) for the evaluation scenario. Each one
# travels the full north->south left corridor, crossing A1 then B1.
EMERGENCY_TIMES = [600, 1200, 1800, 2400]

# elevated-incidence ambulances for training: every ~150 s, alternating
# between a north-south corridor and an east-west one so that every
# junction in the grid gets exposure to emergency traffic.
EMERGENCY_TRAIN_TIMES = [
    (t, "ns_left" if i % 3 == 0 else ("we_top" if i % 3 == 1 else "ns_right"))
    for i, t in enumerate(range(200, EPISODE_SECONDS - 100, 150))
]


def build(scenario: str) -> str:
    d = DEMAND[scenario]
    rate = {
        "ns_left": d["ns"], "ns_right": d["ns"],
        "sn_left": d["ns"], "sn_right": d["ns"],
        "we_top": d["ew"], "we_bottom": d["ew"],
        "ew_top": d["ew"], "ew_bottom": d["ew"],
        "turn_w_to_s": d["turn"], "turn_n_to_e": d["turn"],
        "turn_e_to_s": d["turn"], "turn_s_to_w": d["turn"],
    }

    route_rows = "\n".join(
        f'    <route id="{name}" edges="{edges}"/>' for name, edges in ROUTES.items()
    )
    flow_rows = "\n".join(
        f'    <flow id="f_{name}" type="indian_mix" route="{name}" begin="0" '
        f'end="{EPISODE_SECONDS}" vehsPerHour="{rate[name]}" '
        f'departSpeed="max" departLane="best"/>'
        for name in ROUTES
    )

    emergency_rows = ""
    if scenario == "emergency":
        emergency_rows = "\n".join(
            f'    <vehicle id="ambulance_{i}" type="emergency" route="ns_left" '
            f'depart="{t}" departSpeed="max" departLane="best"/>'
            for i, t in enumerate(EMERGENCY_TIMES)
        )
    elif scenario == "emergency_train":
        emergency_rows = "\n".join(
            f'    <vehicle id="ambulance_{i}" type="emergency" route="{route}" '
            f'depart="{t}" departSpeed="max" departLane="best"/>'
            for i, (t, route) in enumerate(EMERGENCY_TRAIN_TIMES)
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
{VTYPES}
{route_rows}

{flow_rows}

{emergency_rows}
</routes>
"""


SUMOCFG = """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="grid.net.xml"/>
        <route-files value="grid_{scenario}.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{episode}"/>
    </time>
    <processing>
        <time-to-teleport value="300"/>
        <!-- sublane model: lets narrow vehicles (two-wheelers, autos) use
             part of a lane and filter past wider ones. This is what makes
             the heterogeneous mix behave like Indian traffic rather than
             like a queue of differently-sized cars. -->
        <lateral-resolution value="0.8"/>
        <collision.action value="warn"/>
    </processing>
</configuration>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="normal", choices=list(DEMAND.keys()))
    ap.add_argument("--all", action="store_true", help="generate every scenario")
    args = ap.parse_args()

    scenarios = list(DEMAND.keys()) if args.all else [args.scenario]
    for sc in scenarios:
        rou_path = os.path.join(HERE, f"grid_{sc}.rou.xml")
        cfg_path = os.path.join(HERE, f"grid_{sc}.sumocfg")
        with open(rou_path, "w") as f:
            f.write(build(sc))
        with open(cfg_path, "w") as f:
            f.write(SUMOCFG.format(scenario=sc, episode=EPISODE_SECONDS))
        print(f"Wrote {os.path.basename(rou_path)} + {os.path.basename(cfg_path)}")


if __name__ == "__main__":
    main()
