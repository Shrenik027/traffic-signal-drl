"""
Generates the route (demand) file for the single-intersection network, with
DELIBERATELY ASYMMETRIC traffic: North-South gets roughly 2.4x the vehicles
of East-West. This asymmetry matters -- a fixed-timer controller gives every
direction the same green time regardless of how many cars are actually
waiting, so an asymmetric intersection is exactly where a controller that can
*see* the traffic and react to it should have room to beat a timer. A
perfectly balanced intersection would make the fixed timer look artificially
good.

Only straight-through movements are modelled (N<->S, E<->W) to keep the
mini-project scope tight, matching the two-phase traffic light produced by
build_network.py (NS green together, then EW green together). Turning
movements are a natural extension for the major-project phase.

Vehicle *arrival times* within a flow are randomised by SUMO itself at
simulation time (governed by the --seed flag passed to `sumo`), so this file
is deterministic and reproducible: the same file + the same --seed always
produces the same traffic pattern. That reproducibility is what lets
evaluate.py give the fixed-timer baseline and the trained agent an identical
episode to be compared on.

Run:
    python network/build_routes.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Episode length in simulated seconds. Kept short (30 min of traffic) so a
# single training episode finishes quickly during development -- long enough
# to see steady-state queueing behaviour, short enough to iterate fast.
EPISODE_SECONDS = 3000

# vehicles per hour, one direction each (mirrored for the opposite direction)
NS_VEHS_PER_HOUR = 600   # heavier
EW_VEHS_PER_HOUR = 250   # lighter

ROUTES_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">

    <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="5" minGap="2.5" maxSpeed="16.6"/>

    <route id="north_south" edges="N2C C2S"/>
    <route id="south_north" edges="S2C C2N"/>
    <route id="east_west"   edges="E2C C2W"/>
    <route id="west_east"   edges="W2C C2E"/>

    <!-- North-South: the heavy direction -->
    <flow id="ns" type="car" route="north_south" begin="0" end="{EPISODE_SECONDS}"
          vehsPerHour="{NS_VEHS_PER_HOUR}" departSpeed="max" departLane="best"/>
    <flow id="sn" type="car" route="south_north" begin="0" end="{EPISODE_SECONDS}"
          vehsPerHour="{NS_VEHS_PER_HOUR}" departSpeed="max" departLane="best"/>

    <!-- East-West: the light direction -->
    <flow id="ew" type="car" route="east_west" begin="0" end="{EPISODE_SECONDS}"
          vehsPerHour="{EW_VEHS_PER_HOUR}" departSpeed="max" departLane="best"/>
    <flow id="we" type="car" route="west_east" begin="0" end="{EPISODE_SECONDS}"
          vehsPerHour="{EW_VEHS_PER_HOUR}" departSpeed="max" departLane="best"/>

</routes>
"""

SUMOCFG_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="intersection.net.xml"/>
        <route-files value="intersection.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{EPISODE_SECONDS}"/>
    </time>
    <processing>
        <time-to-teleport value="300"/>
    </processing>
</configuration>
"""


def main():
    rou_path = os.path.join(HERE, "intersection.rou.xml")
    cfg_path = os.path.join(HERE, "intersection.sumocfg")

    with open(rou_path, "w") as f:
        f.write(ROUTES_XML)
    with open(cfg_path, "w") as f:
        f.write(SUMOCFG_XML)

    print(f"Wrote {rou_path}")
    print(f"Wrote {cfg_path}")
    print(f"Episode length: {EPISODE_SECONDS}s | NS: {NS_VEHS_PER_HOUR} veh/h/dir | EW: {EW_VEHS_PER_HOUR} veh/h/dir")


if __name__ == "__main__":
    main()
