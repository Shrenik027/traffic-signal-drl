"""
STAGE C, novelty part two — EMERGENCY-VEHICLE PRIORITY.

This module is what turns a generic queue-clearing agent into one that
opens a green corridor for an ambulance. It contains exactly two things,
and the pair of them is the whole idea:

  1. EmergencyObservationFunction — the agent must be able to SEE an
     approaching ambulance, or no reward can teach it to react. We extend
     sumo-rl's default per-junction observation with, for every incoming
     lane, (a) a flag for "an emergency vehicle is on this lane" and (b)
     how close to the stop line it is, 0 (far) to 1 (at the line).
     Detection is done live through TraCI, which is the mechanism
     MASTER-GUIDE.md Step 17 specifies.

  2. emergency_reward — the agent must be PUNISHED for making an ambulance
     wait, hard enough to outweigh the ordinary traffic it will inconvenience
     by holding a green. The reward keeps the ordinary diff-waiting-time
     term (so normal traffic still matters) and subtracts a heavily weighted
     emergency-delay term.

The balance between those two terms is the entire craft here, and it is
what MASTER-GUIDE.md Step 17's "watch out" warns about: weight the
emergency term too low and the ambulance is treated like any other vehicle;
too high and the agent will happily gridlock a whole junction to shave a
second off an ambulance that is still 200 m away. EMERGENCY_WEIGHT below is
the knob; the evaluation study reports what it cost ordinary traffic.
"""
import numpy as np
from gymnasium import spaces
from sumo_rl.environment.observations import ObservationFunction
from sumo_rl.environment.traffic_signal import TrafficSignal

# Vehicle type id used for ambulances in the route files.
EMERGENCY_VTYPE = "emergency"

# How heavily an emergency vehicle's delay counts relative to ordinary
# traffic's. Ordinary reward is (waiting-time delta)/100 summed over lanes;
# this term is (emergency waiting seconds)/10, so one second of ambulance
# delay is worth roughly ten vehicle-seconds of ordinary delay.
EMERGENCY_WEIGHT = 1.0

# Only react to an ambulance once it is within this distance of the stop
# line. Beyond it, holding a green "just in case" wrecks normal traffic for
# no benefit.
DETECTION_RANGE_M = 150.0


def _emergency_state(ts: TrafficSignal):
    """Per-lane (presence, closeness, waiting_time) for emergency vehicles.

    closeness is 1.0 at the stop line and decays to 0.0 at DETECTION_RANGE_M.
    Uses TraCI directly -- this is the 'detect the ambulance' step.
    """
    presence, closeness, waiting = [], [], []
    for lane in ts.lanes:
        lane_len = ts.lanes_length[lane]
        best_close, is_present, wait = 0.0, 0.0, 0.0
        for veh in ts.sumo.lane.getLastStepVehicleIDs(lane):
            if ts.sumo.vehicle.getTypeID(veh) != EMERGENCY_VTYPE:
                continue
            # distance from the vehicle to the end of the lane (the stop line)
            dist_to_stopline = lane_len - ts.sumo.vehicle.getLanePosition(veh)
            if dist_to_stopline > DETECTION_RANGE_M:
                continue
            is_present = 1.0
            best_close = max(best_close, 1.0 - dist_to_stopline / DETECTION_RANGE_M)
            wait += ts.sumo.vehicle.getAccumulatedWaitingTime(veh)
        presence.append(is_present)
        closeness.append(best_close)
        waiting.append(wait)
    return presence, closeness, waiting


class EmergencyObservationFunction(ObservationFunction):
    """Default sumo-rl observation + emergency-vehicle awareness.

    Layout (all values in [0, 1]):
        [ one-hot current green phase        ] num_green_phases
        [ min-green elapsed flag             ] 1
        [ density per incoming lane          ] len(lanes)
        [ queue per incoming lane            ] len(lanes)
        [ emergency present per lane         ] len(lanes)   <-- new
        [ emergency closeness per lane       ] len(lanes)   <-- new
    """

    def __init__(self, ts: TrafficSignal):
        super().__init__(ts)

    def __call__(self) -> np.ndarray:
        phase_id = [1 if self.ts.green_phase == i else 0 for i in range(self.ts.num_green_phases)]
        min_green = [
            0 if self.ts.time_since_last_phase_change < self.ts.min_green + self.ts.yellow_time else 1
        ]
        density = self.ts.get_lanes_density()
        queue = self.ts.get_lanes_queue()
        presence, closeness, _ = _emergency_state(self.ts)
        return np.array(
            phase_id + min_green + density + queue + presence + closeness,
            dtype=np.float32,
        )

    def observation_space(self) -> spaces.Box:
        n = self.ts.num_green_phases + 1 + 4 * len(self.ts.lanes)
        return spaces.Box(low=np.zeros(n, dtype=np.float32), high=np.ones(n, dtype=np.float32))


def emergency_reward(ts: TrafficSignal) -> float:
    """Ordinary waiting-time reward, minus a heavy penalty for delaying
    any emergency vehicle on this junction's approaches.

    The first term is sumo-rl's standard 'diff-waiting-time': the drop in
    accumulated waiting time since the last decision (positive = things got
    better). The second term is what creates the green corridor.
    """
    # --- ordinary traffic term (identical to sumo-rl's diff-waiting-time) ---
    ts_wait = sum(ts.get_accumulated_waiting_time_per_lane()) / 100.0
    ordinary = ts.last_measure - ts_wait
    ts.last_measure = ts_wait

    # --- emergency term ---
    _, _, waiting = _emergency_state(ts)
    emergency_delay = sum(waiting) / 10.0

    return ordinary - EMERGENCY_WEIGHT * emergency_delay
