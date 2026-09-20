"use client";

import { useEffect, useState } from "react";
import {CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, XAxis, YAxis, } from "recharts";
import { ApiState, useApi } from "../../lib/useApi";
import EmptyState from "../EmptyState";
import { ChartTip, GRID_STROKE, TICK } from "../ChartKit";

interface ComparePoint {
  hunt_id: number; date: string;
  scope_dps: number; party_dps: number;
  avg_scope_dps: number; avg_party_dps: number;
}
interface CompareData { points: ComparePoint[]; window: number; scope: string[]; }

export default function CompareView({ scope, variantId, clearScope, partySize }: { scope: number[]; variantId: number | string | null; clearScope: () => void; partySize: number | null }) {
  const { data, error, loading } = useApi<CompareData>(
    "/compare",
    scope.length === 0 ? null : {
      player_ids: scope.join(","),
      ...(variantId !== null && { variant_id: variantId }),
      ...(partySize != null && { players: partySize }),
    });

  if (scope.length === 0) {
    return (
      <EmptyState what="comparison scope">
        <p>Star yourself (and your hunting buddies) with ★ in the hunters bar above, then add them to the scope.</p>
      </EmptyState>
    );
  }
  if (error || loading || !data) return <ApiState error={error} loading={loading} />;
  if (data.points.length === 0) {
    return (
      <EmptyState what="hunts for this scope">
        <p>No hunts include {data.scope.join(", ") || "these hunters"} yet.</p>
        <p><button type="button" onClick={clearScope}>Clear hunter scope</button></p>
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
          <CartesianGrid stroke={GRID_STROKE} />
          <XAxis dataKey="x" tick={TICK} interval="preserveStartEnd" />
          <YAxis tick={TICK}
            label={{ value: "DPS", fill: "var(--chart-tick, #9aa1b2)", fontSize: 11, angle: -90, position: "insideLeft" }} />
          <ChartTip />
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
