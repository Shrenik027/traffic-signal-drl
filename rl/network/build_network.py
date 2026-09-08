"""
Builds the single 4-way intersection SUMO network used for the mini-project
milestone: one traffic-light-controlled junction with N/S/E/W approaches.

Why hand-written nodes/edges instead of netgenerate's --grid or --spider:
those tools are built for *multiple* connected junctions (a city block or a
grid of intersections). Getting them to produce exactly ONE isolated 4-way
crossroad with no extra ring roads or T-junctions turned out to need more
fighting-the-tool than just writing the five nodes and eight edges directly
in SUMO's plain-text node/edge format and handing them to `netconvert`
(the standard SUMO network compiler). This is the same workflow SUMO's own
tutorials use for small hand-built networks.

Layout:

              N
              |
      W ----- C ----- E
              |
              S

Run:
    python network/build_network.py

Produces (in this folder):
    intersection.net.xml   -- the compiled network (nodes + edges + TLS)
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

NODES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<nodes>
    <node id="C" x="0" y="0" type="traffic_light"/>
    <node id="N" x="0" y="200" type="priority"/>
    <node id="S" x="0" y="-200" type="priority"/>
    <node id="E" x="200" y="0" type="priority"/>
    <node id="W" x="-200" y="0" type="priority"/>
</nodes>
"""

# Two lanes per direction, 13.89 m/s (~50 km/h) speed limit -- a typical
# urban arterial. Each arm has one edge INTO the center and one edge OUT OF
# the center, so vehicles can both arrive at and leave through every arm.
EDGES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edges>
    <edge id="N2C" from="N" to="C" numLanes="2" speed="13.89"/>
    <edge id="C2N" from="C" to="N" numLanes="2" speed="13.89"/>
    <edge id="S2C" from="S" to="C" numLanes="2" speed="13.89"/>
    <edge id="C2S" from="C" to="S" numLanes="2" speed="13.89"/>
    <edge id="E2C" from="E" to="C" numLanes="2" speed="13.89"/>
    <edge id="C2E" from="C" to="E" numLanes="2" speed="13.89"/>
    <edge id="W2C" from="W" to="C" numLanes="2" speed="13.89"/>
    <edge id="C2W" from="C" to="W" numLanes="2" speed="13.89"/>
</edges>
"""


def main():
    nod_path = os.path.join(HERE, "intersection.nod.xml")
    edg_path = os.path.join(HERE, "intersection.edg.xml")
    net_path = os.path.join(HERE, "intersection.net.xml")

    with open(nod_path, "w") as f:
        f.write(NODES_XML)
    with open(edg_path, "w") as f:
        f.write(EDGES_XML)

    cmd = [
        "netconvert",
        "--node-files", nod_path,
        "--edge-files", edg_path,
        "--output-file", net_path,
        "--tls.guess", "true",       # auto-build the traffic-light logic at C
        "--no-turnarounds", "true",  # no U-turns at the junction
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\nNetwork written to {net_path}")


if __name__ == "__main__":
    main()
