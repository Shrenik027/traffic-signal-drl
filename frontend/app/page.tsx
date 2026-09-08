"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* Categorical slots, fixed order, one hue per entity — never reassigned
   when a chart's series set changes. Mirrors the CSS custom properties. */
const C = {
  fixed: "#2a78d6",
  agent: "#eb6834",
  agentEmergency: "#1baf7a",
};

const LABEL = {
  fixed: "Fixed timer",
  agent: "RL agent",
  agent_emergency: "Emergency-aware agent",
} as const;

const AXIS = { fontSize: 12, fill: "#52514e" };

/* ---------------------------------------------------------------- types */

type Cell = {
  avg_waiting_time: number;
  std_waiting_time: number;
  avg_vehicles_cleared: number;
  avg_queue_length: number;
  by_vehicle_type?: Record<string, number>;
  emergency?: {
    avg_waiting_time: number;
    avg_clearance_time: number;
    std_clearance_time: number;
  };
};

type ScenarioBlock = {
  fixed: Cell;
  agent: Cell;
  agent_emergency?: Cell;
  improvement_pct: number;
  emergency_improvement_pct?: number;
};

type GridMetrics = {
  seeds: number[];
  network: string;
  traffic: string;
  scenarios: Record<string, ScenarioBlock>;
  timeseries: Record<"fixed" | "agent", { step: number; wait: number }[]>;
};

type SingleMetrics = {
  seeds: number[];
  baseline: { avg_waiting_time: number; std_waiting_time: number; avg_vehicles_cleared: number };
  agent: { avg_waiting_time: number; std_waiting_time: number; avg_vehicles_cleared: number };
  improvement_pct: number;
  timeseries: { step: number; baseline_waiting_time: number; agent_waiting_time: number }[];
  timeseries_seed: number;
};

/* ------------------------------------------------------------ fragments */

function Legend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span className="legend-item" key={i.label}>
          <span className="swatch" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

function ChartTooltip({ active, payload, label, unit = "s" }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <div className="tooltip-label">{label}</div>
      {payload.map((p: any) => (
        <div className="tooltip-row" key={p.dataKey}>
          <span className="swatch" style={{ background: p.color || p.fill }} />
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(2) : p.value}
          {unit}
        </div>
      ))}
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  );
}

/* --------------------------------------------------------- grid section */

function GridView({ d }: { d: GridMetrics }) {
  const order = ["light", "normal", "heavy", "emergency"];
  const scenarioData = order
    .filter((s) => d.scenarios[s])
    .map((s) => ({
      scenario: s[0].toUpperCase() + s.slice(1),
      fixed: d.scenarios[s].fixed.avg_waiting_time,
      agent: d.scenarios[s].agent.avg_waiting_time,
      improvement: d.scenarios[s].improvement_pct,
    }));

  const normal = d.scenarios.normal;
  const emergency = d.scenarios.emergency;

  // waiting time per vehicle class — the heterogeneous-traffic view
  const typeNames: Record<string, string> = {
    motorcycle: "Two-wheeler",
    car: "Car",
    auto: "Auto-rickshaw",
    bus: "Bus",
  };
  const typeData = Object.keys(normal.fixed.by_vehicle_type || {})
    .filter((k) => k in typeNames)
    .map((k) => ({
      type: typeNames[k],
      fixed: normal.fixed.by_vehicle_type![k],
      agent: normal.agent.by_vehicle_type?.[k] ?? 0,
    }));

  // ambulance clearance, three controllers
  const ambulance = emergency
    ? (["fixed", "agent", "agent_emergency"] as const)
        .filter((c) => emergency[c]?.emergency)
        .map((c) => ({
          controller: LABEL[c],
          value: emergency[c]!.emergency!.avg_clearance_time,
          fill: c === "fixed" ? C.fixed : c === "agent" ? C.agent : C.agentEmergency,
        }))
    : [];

  const merged = (d.timeseries?.fixed || []).map((p, i) => ({
    step: p.step,
    fixed: p.wait,
    agent: d.timeseries?.agent?.[i]?.wait ?? null,
  }));

  return (
    <>
      <div className="tiles">
        <Tile
          label="Waiting time, normal demand"
          value={`${normal.improvement_pct}%`}
          sub={`lower than fixed timing (${normal.fixed.avg_waiting_time}s → ${normal.agent.avg_waiting_time}s)`}
        />
        <Tile
          label="Waiting time, peak demand"
          value={`${d.scenarios.heavy.improvement_pct}%`}
          sub={`lower than fixed timing (${d.scenarios.heavy.fixed.avg_waiting_time}s → ${d.scenarios.heavy.agent.avg_waiting_time}s)`}
        />
        {emergency?.emergency_improvement_pct !== undefined && (
          <Tile
            label="Ambulance clearance"
            value={`${emergency.emergency_improvement_pct}%`}
            sub={`faster end-to-end than fixed timing`}
          />
        )}
        <Tile
          label="Junctions controlled"
          value="4"
          sub="one shared policy, 2×2 grid"
        />
      </div>

      <div className="card">
        <p className="card-title">Average waiting time by demand scenario</p>
        <p className="card-sub">
          Mean over seeds {d.seeds.join(", ")} · identical traffic for both controllers · lower is
          better
        </p>
        <Legend
          items={[
            { color: C.fixed, label: LABEL.fixed },
            { color: C.agent, label: LABEL.agent },
          ]}
        />
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={scenarioData} barGap={2} margin={{ top: 16, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#ebebe8" vertical={false} />
            <XAxis dataKey="scenario" tick={AXIS} tickLine={false} axisLine={{ stroke: "#e5e5e1" }} />
            <YAxis
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={44}
              label={{ value: "seconds", angle: -90, position: "insideLeft", ...AXIS }}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(0,0,0,0.035)" }} />
            <Bar dataKey="fixed" name={LABEL.fixed} fill={C.fixed} radius={[4, 4, 0, 0]} maxBarSize={46} />
            <Bar dataKey="agent" name={LABEL.agent} fill={C.agent} radius={[4, 4, 0, 0]} maxBarSize={46} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <p className="card-title">Mean waiting time through the episode</p>
        <p className="card-sub">
          Normal demand · seed {d.seeds[0]} · the fixed timer&apos;s sawtooth is its cycle building
          and flushing queues regardless of who is waiting
        </p>
        <Legend
          items={[
            { color: C.fixed, label: LABEL.fixed },
            { color: C.agent, label: LABEL.agent },
          ]}
        />
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={merged} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#ebebe8" vertical={false} />
            <XAxis
              dataKey="step"
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: "#e5e5e1" }}
              tickFormatter={(v) => `${Math.round(v / 60)}m`}
            />
            <YAxis
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={44}
              label={{ value: "seconds", angle: -90, position: "insideLeft", ...AXIS }}
            />
            <Tooltip
              content={<ChartTooltip />}
              labelFormatter={(v) => `t = ${v}s`}
              cursor={{ stroke: "#c9c8c3", strokeWidth: 1 }}
            />
            <Line
              type="monotone"
              dataKey="fixed"
              name={LABEL.fixed}
              stroke={C.fixed}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "#fcfcfb" }}
            />
            <Line
              type="monotone"
              dataKey="agent"
              name={LABEL.agent}
              stroke={C.agent}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "#fcfcfb" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid-2">
        <div className="card">
          <p className="card-title">Waiting time by vehicle class</p>
          <p className="card-sub">
            Normal demand · {d.traffic.replace("heterogeneous ", "")}
          </p>
          <Legend
            items={[
              { color: C.fixed, label: LABEL.fixed },
              { color: C.agent, label: LABEL.agent },
            ]}
          />
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={typeData} barGap={2} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#ebebe8" vertical={false} />
              <XAxis dataKey="type" tick={{ ...AXIS, fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#e5e5e1" }} interval={0} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} width={40} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(0,0,0,0.035)" }} />
              <Bar dataKey="fixed" name={LABEL.fixed} fill={C.fixed} radius={[4, 4, 0, 0]} maxBarSize={34} />
              <Bar dataKey="agent" name={LABEL.agent} fill={C.agent} radius={[4, 4, 0, 0]} maxBarSize={34} />
            </BarChart>
          </ResponsiveContainer>
          <p className="footnote">
            Buses and auto-rickshaws clear a stop line more slowly than two-wheelers, so the mix
            itself — not just the vehicle count — shapes how much green each approach needs.
          </p>
        </div>

        <div className="card">
          <p className="card-title">Ambulance clearance time</p>
          <p className="card-sub">
            End-to-end journey through the corridor · lower is better
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={ambulance}
              layout="vertical"
              margin={{ top: 8, right: 48, left: 8, bottom: 0 }}
            >
              <CartesianGrid stroke="#ebebe8" horizontal={false} />
              <XAxis type="number" tick={AXIS} tickLine={false} axisLine={{ stroke: "#e5e5e1" }} />
              <YAxis
                type="category"
                dataKey="controller"
                tick={{ ...AXIS, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={132}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(0,0,0,0.035)" }} />
              <Bar
                dataKey="value"
                name="Clearance time"
                radius={[0, 4, 4, 0]}
                maxBarSize={34}
                label={{ position: "right", fontSize: 12, fill: "#0b0b0b", formatter: (v: number) => `${v.toFixed(1)}s` }}
              />
            </BarChart>
          </ResponsiveContainer>
          <p className="footnote">
            The middle bar is the ablation: an agent trained without the emergency reward term
            treats an ambulance like any other vehicle.
          </p>
        </div>
      </div>

      <div className="card">
        <p className="card-title">Full results</p>
        <p className="card-sub">
          Mean ± standard deviation across seeds {d.seeds.join(", ")} · {d.network}
        </p>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Controller</th>
                <th className="num">Avg wait (s)</th>
                <th className="num">Avg queue</th>
                <th className="num">Vehicles cleared</th>
                <th className="num">Improvement</th>
              </tr>
            </thead>
            <tbody>
              {order
                .filter((s) => d.scenarios[s])
                .flatMap((s) => {
                  const blk = d.scenarios[s];
                  const rows: (readonly [string, Cell])[] = [
                    ["fixed", blk.fixed],
                    ["agent", blk.agent],
                  ];
                  if (blk.agent_emergency) rows.push(["agent_emergency", blk.agent_emergency]);
                  return rows.map(([key, cell], i) => (
                    <tr key={`${s}-${key}`}>
                      <td>{i === 0 ? s[0].toUpperCase() + s.slice(1) : ""}</td>
                      <td>
                        <span
                          className="swatch"
                          style={{
                            display: "inline-block",
                            marginRight: 7,
                            background:
                              key === "fixed" ? C.fixed : key === "agent" ? C.agent : C.agentEmergency,
                          }}
                        />
                        {LABEL[key as keyof typeof LABEL]}
                      </td>
                      <td className={`num ${key !== "fixed" ? "win" : ""}`}>
                        {cell.avg_waiting_time.toFixed(2)} ± {cell.std_waiting_time.toFixed(2)}
                      </td>
                      <td className="num">{cell.avg_queue_length.toFixed(1)}</td>
                      <td className="num">{cell.avg_vehicles_cleared.toFixed(0)}</td>
                      <td className="num">{key === "agent" ? `${blk.improvement_pct}%` : ""}</td>
                    </tr>
                  ));
                })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

/* ------------------------------------------------- single-intersection */

function SingleView({ d }: { d: SingleMetrics }) {
  const data = d.timeseries.map((p) => ({
    step: p.step,
    fixed: p.baseline_waiting_time,
    agent: p.agent_waiting_time,
  }));
  return (
    <>
      <div className="tiles">
        <Tile
          label="Fixed timer"
          value={`${d.baseline.avg_waiting_time}s`}
          sub={`±${d.baseline.std_waiting_time}s · ${d.baseline.avg_vehicles_cleared} vehicles cleared`}
        />
        <Tile
          label="RL agent (DQN)"
          value={`${d.agent.avg_waiting_time}s`}
          sub={`±${d.agent.std_waiting_time}s · ${d.agent.avg_vehicles_cleared} vehicles cleared`}
        />
        <Tile label="Improvement" value={`${d.improvement_pct}%`} sub="lower average waiting time" />
      </div>

      <div className="card">
        <p className="card-title">Mean waiting time through the episode</p>
        <p className="card-sub">
          Single 4-way intersection · asymmetric N–S / E–W demand · seed {d.timeseries_seed}
        </p>
        <Legend
          items={[
            { color: C.fixed, label: LABEL.fixed },
            { color: C.agent, label: LABEL.agent },
          ]}
        />
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#ebebe8" vertical={false} />
            <XAxis
              dataKey="step"
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: "#e5e5e1" }}
              tickFormatter={(v) => `${Math.round(v / 60)}m`}
            />
            <YAxis
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={44}
              label={{ value: "seconds", angle: -90, position: "insideLeft", ...AXIS }}
            />
            <Tooltip content={<ChartTooltip />} labelFormatter={(v) => `t = ${v}s`} cursor={{ stroke: "#c9c8c3" }} />
            <Line type="monotone" dataKey="fixed" name={LABEL.fixed} stroke={C.fixed} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "#fcfcfb" }} />
            <Line type="monotone" dataKey="agent" name={LABEL.agent} stroke={C.agent} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "#fcfcfb" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

/* --------------------------------------------------------------- page */

export default function Home() {
  const [tab, setTab] = useState<"grid" | "single">("grid");
  const [grid, setGrid] = useState<GridMetrics | null>(null);
  const [single, setSingle] = useState<SingleMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/results/grid`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`grid: ${r.status}`))))
      .then(setGrid)
      .catch((e) => setError(e.message));
    fetch(`${API_URL}/api/results`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`single: ${r.status}`))))
      .then(setSingle)
      .catch(() => {});
  }, []);

  return (
    <main className="page">
      <h1>Self-Learning Adaptive Traffic Signal Control</h1>
      <p className="lede">
        A reinforcement-learning agent controlling signalised junctions in SUMO, measured against
        conventional fixed-time control on identical simulated traffic. Heterogeneous Indian
        vehicle mix, with emergency-vehicle priority.
      </p>

      <div className="tabs">
        <button className="tab" data-active={tab === "grid"} onClick={() => setTab("grid")}>
          Grid study (4 junctions)
        </button>
        <button className="tab" data-active={tab === "single"} onClick={() => setTab("single")}>
          Single intersection
        </button>
      </div>

      {tab === "grid" &&
        (grid ? (
          <GridView d={grid} />
        ) : (
          <div className="state-msg">
            {error ? (
              <>
                Couldn&apos;t load results from {API_URL}.<br />
                Start the backend with <code>uvicorn main:app --port 8000</code> and make sure{" "}
                <code>python evaluate_grid.py</code> has been run.
              </>
            ) : (
              "Loading grid results…"
            )}
          </div>
        ))}

      {tab === "single" &&
        (single ? (
          <SingleView d={single} />
        ) : (
          <div className="state-msg">
            Single-intersection results not found — run <code>python evaluate.py</code> in /rl.
          </div>
        ))}
    </main>
  );
}
