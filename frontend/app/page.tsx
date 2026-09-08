"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Metrics = {
  seeds: number[];
  baseline: {
    avg_waiting_time: number;
    std_waiting_time: number;
    avg_vehicles_cleared: number;
  };
  agent: {
    avg_waiting_time: number;
    std_waiting_time: number;
    avg_vehicles_cleared: number;
  };
  improvement_pct: number;
  timeseries: { step: number; baseline_waiting_time: number; agent_waiting_time: number }[];
  timeseries_seed: number;
};

export default function Home() {
  const [data, setData] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/results`)
      .then((res) => {
        if (!res.ok) throw new Error(`Backend returned ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <main className="page">
        <div className="title">Traffic-RL Dashboard</div>
        <div className="state-msg">
          Couldn&apos;t reach the backend at {API_URL}.<br />
          Make sure it&apos;s running: <code>uvicorn main:app --reload --port 8000</code>
          <br />
          <br />
          {error}
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="page">
        <div className="title">Traffic-RL Dashboard</div>
        <div className="state-msg">Loading results…</div>
      </main>
    );
  }

  const improved = data.improvement_pct > 0;

  return (
    <main className="page">
      <div className="title">Fixed Timer vs Self-Learning Agent</div>
      <div className="subtitle">
        Single 4-way intersection · asymmetric N-S/E-W demand · matched random
        seeds {data.seeds.join(", ")}
      </div>

      <div className={`improvement ${improved ? "" : "negative"}`}>
        {improved
          ? `Agent reduces average waiting time by ${data.improvement_pct}%`
          : `Agent is ${Math.abs(data.improvement_pct)}% worse than the fixed timer`}
      </div>

      <div className="cards">
        <div className="card">
          <div className="card-label">Fixed Timer</div>
          <div className="card-value">{data.baseline.avg_waiting_time}s</div>
          <div className="card-sub">avg waiting time / vehicle</div>
          <div className="card-sub">
            ±{data.baseline.std_waiting_time}s · {data.baseline.avg_vehicles_cleared} vehicles cleared
          </div>
        </div>
        <div className="card agent">
          <div className="card-label">Self-Learning Agent (DQN)</div>
          <div className="card-value">{data.agent.avg_waiting_time}s</div>
          <div className="card-sub">avg waiting time / vehicle</div>
          <div className="card-sub">
            ±{data.agent.std_waiting_time}s · {data.agent.avg_vehicles_cleared} vehicles cleared
          </div>
        </div>
      </div>

      <div className="chart-card">
        <div className="chart-title">Mean waiting time over the episode</div>
        <div className="chart-sub">
          seed {data.timeseries_seed} · lower is better · sampled every 5 simulated seconds
        </div>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={data.timeseries} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis
              dataKey="step"
              tickFormatter={(v) => `${Math.round(v / 60)}m`}
              label={{ value: "simulated time", position: "insideBottom", offset: -2, fontSize: 12 }}
              fontSize={12}
            />
            <YAxis
              label={{ value: "mean waiting time (s)", angle: -90, position: "insideLeft", fontSize: 12 }}
              fontSize={12}
            />
            <Tooltip formatter={(v: number) => `${v}s`} labelFormatter={(v) => `t=${v}s`} />
            <Legend />
            <Line
              type="monotone"
              dataKey="baseline_waiting_time"
              name="Fixed Timer"
              stroke="#9aa0a6"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="agent_waiting_time"
              name="Self-Learning Agent"
              stroke="#1c7a3d"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </main>
  );
}
