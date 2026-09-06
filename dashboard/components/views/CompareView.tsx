"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet } from "../../lib/api";
import EmptyState from "../EmptyState";

interface ComparePoint {
  hunt_id: number; date: string;
  scope_dps: number; party_dps: number;
  avg_scope_dps: number; avg_party_dps: number;
}
interface CompareData { points: ComparePoint[]; window: number; scope: string[]; }

export default function CompareView({ scope }: { scope: number[] }) {
  const [data, setData] = useState<CompareData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = scope.join(",");

  useEffect(() => {
    if (scope.length === 0) { setData(null); return; }
    apiGet<CompareData>("/compare", { player_ids: scope.join(",") })
      .then(setData)
      .catch((e: Error) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (scope.length === 0) {
    return (
      <EmptyState what="comparison scope">
        <p>Star yourself (and your hunting buddies) with ★ in the hunters bar above, then add them to the scope.</p>
      </EmptyState>
    );
  }
  if (error) return <p className="error">{error} — is the API running?</p>;
  if (!data) return <p>Loading…</p>;
  if (data.points.length === 0) {
    return (
      <EmptyState what="hunts for this scope">
        <p>No hunts include {data.scope.join(", ") || "these hunters"} yet.</p>
      </EmptyState>
    );
  }

  const rows = data.points.map((p) => ({
    x: `#${p.hunt_id} ${p.date}`,
    you: Math.round(p.scope_dps * 10) / 10,
    party: Math.round(p.party_dps * 10) / 10,
    youAvg: Math.round(p.avg_scope_dps * 10) / 10,
    partyAvg: Math.round(p.avg_party_dps * 10) / 10,
  }));
  const label = data.scope.join(" + ") || "scope";

  return (
    <div className="card">
      <h2>{label} vs party ({data.points.length} hunts, {data.window}-hunt rolling)</h2>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={rows}>
          <CartesianGrid stroke="#2c313e" />
          <XAxis dataKey="x" tick={{ fill: "#9aa1b2", fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: "#9aa1b2", fontSize: 11 }}
            label={{ value: "DPS", fill: "#9aa1b2", fontSize: 11, angle: -90, position: "insideLeft" }} />
          <Tooltip contentStyle={{ background: "#1d2029", border: "1px solid #2c313e" }} />
          <Legend />
          <Line type="monotone" dataKey="you" name={label} stroke="#e8b64c" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="party" name="party avg" stroke="#5aa9e6" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="youAvg" name={`${label} rolling`} stroke="#e8b64c" dot={false} strokeDasharray="6 3" strokeWidth={1} />
          <Line type="monotone" dataKey="partyAvg" name="party rolling" stroke="#5aa9e6" dot={false} strokeDasharray="6 3" strokeWidth={1} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
