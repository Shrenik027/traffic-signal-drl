"""
STAGE C — builds the multi-intersection network: a 2x2 grid of four
signalised junctions (an urban corridor block), which is the step up from
the single intersection of the mini-project.

Why 2x2 and not a bigger grid: MASTER-GUIDE.md Step 14 says it explicitly --
"multi-agent is unstable, start with 2 intersections before a full grid."
Four junctions is the smallest network that actually contains the hard
part we need to demonstrate: signals whose decisions SPILL INTO EACH OTHER.
When A1 releases a platoon eastward, that platoon becomes A2's problem two
hundred metres later. A controller that only optimises its own junction can
make its neighbour worse -- that coupling is the whole reason multi-agent
traffic control is a research problem and not just four copies of the
mini-project.

Layout (300 m between junctions, fringe nodes 300 m further out):

           N1        N2
            |         |
    W1 --- A1 ------ A2 --- E1
            |         |
    W2 --- B1 ------ B2 --- E2
            |         |
           S1        S2

  A1 A2 B1 B2 = the four traffic-light-controlled junctions (our agents)
  N*, S*, E*, W* = fringe nodes where traffic enters and leaves

Run:
    python network/build_grid.py
Produces:
    grid.net.xml
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

SPACING = 300  # metres between adjacent junctions

NODES_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<nodes>
    <!-- the four controlled junctions -->
    <node id="A1" x="0"        y="{SPACING}"  type="traffic_light"/>
    <node id="A2" x="{SPACING}" y="{SPACING}"  type="traffic_light"/>
    <node id="B1" x="0"        y="0"          type="traffic_light"/>
    <node id="B2" x="{SPACING}" y="0"          type="traffic_light"/>

    <!-- fringe: sources and sinks -->
    <node id="N1" x="0"          y="{2 * SPACING}"  type="priority"/>
    <node id="N2" x="{SPACING}"   y="{2 * SPACING}"  type="priority"/>
    <node id="S1" x="0"          y="{-SPACING}"     type="priority"/>
    <node id="S2" x="{SPACING}"   y="{-SPACING}"     type="priority"/>
    <node id="W1" x="{-SPACING}"  y="{SPACING}"      type="priority"/>
    <node id="W2" x="{-SPACING}"  y="0"              type="priority"/>
    <node id="E1" x="{2 * SPACING}" y="{SPACING}"    type="priority"/>
    <node id="E2" x="{2 * SPACING}" y="0"            type="priority"/>
</nodes>
"""

# Two lanes per direction everywhere. 13.89 m/s = 50 km/h urban arterial.
_PAIRS = [
    ("N1", "A1"), ("N2", "A2"),          # north approaches
    ("S1", "B1"), ("S2", "B2"),          # south approaches
    ("W1", "A1"), ("W2", "B1"),          # west approaches
    ("E1", "A2"), ("E2", "B2"),          # east approaches
    ("A1", "A2"), ("B1", "B2"),          # internal horizontal links
    ("A1", "B1"), ("A2", "B2"),          # internal vertical links
]


def _edges_xml() -> str:
    rows = []
    for a, b in _PAIRS:
        rows.append(f'    <edge id="{a}{b}" from="{a}" to="{b}" numLanes="2" speed="13.89"/>')
        rows.append(f'    <edge id="{b}{a}" from="{b}" to="{a}" numLanes="2" speed="13.89"/>')
    body = "\n".join(rows)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<edges>\n{body}\n</edges>\n'


def main():
    nod_path = os.path.join(HERE, "grid.nod.xml")
    edg_path = os.path.join(HERE, "grid.edg.xml")
    net_path = os.path.join(HERE, "grid.net.xml")

    with open(nod_path, "w") as f:
        f.write(NODES_XML)
    with open(edg_path, "w") as f:
        f.write(_edges_xml())

    cmd = [
        "netconvert",
        "--node-files", nod_path,
        "--edge-files", edg_path,
        "--output-file", net_path,
        "--tls.guess", "true",
        "--tls.default-type", "static",
        "--no-turnarounds", "true",
        # give every junction the SAME simple 2-phase program, so the
        # fixed-timer baseline is a uniform, uncoordinated timer -- the
        # honest "what a city actually deploys" comparison point.
        "--tls.cycle.time", "90",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\nGrid network written to {net_path}")


if __name__ == "__main__":
    main()
