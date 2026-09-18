import type { Metric } from "../lib/metrics";

export interface ChartEvent {
  type: string; start: number; end: number | null;
  monster?: string | null;
}

interface TooltipEntry { name?: unknown; value?: unknown; color?: string; }

/** Dark chart hover card shared by Damage curves and the Hunts popup:
 *  per-player values (DPS modes get one decimal + unit) plus badges for
 *  whichever monsters are enraged at the hovered time. Enrage bands
 *  themselves carry no text (they overlap); identity comes from these
 *  badges. Dark background keeps bright series colors readable. */
export default function ChartTooltip({ active, payload, label, metric, events, colorOf }: {
  active?: boolean; payload?: TooltipEntry[]; label?: number | string;
  metric: Metric; events: ChartEvent[]; colorOf: (e: ChartEvent) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const t = typeof label === "number" ? label : Number(label);
  const enraged = new Map<string, string>();
  if (Number.isFinite(t)) {
    for (const e of events) {
      if (e.type !== "enrage") continue;
      if (t >= e.start - 1e-9 && (e.end == null || t <= e.end + 1e-9)) {
        const m = e.monster ?? "";
        if (m && !enraged.has(m)) enraged.set(m, colorOf(e));
      }
    }
  }
  const fmt = (p: TooltipEntry) => {
    const name = String(p.name ?? "");
    if (name.includes(" HP") && typeof p.value === "number")
      return `${(p.value * 100).toFixed(1)}%`;
    if (typeof p.value !== "number") return String(p.value ?? "");
    return metric === "damage"
      ? Math.round(p.value).toLocaleString()
      : `${p.value.toFixed(1)} DPS`;
  };
  return (
    <div style={{ background: "#1d2029", border: "1px solid #2c313e", padding: "8px 10px", fontSize: 12 }}>
      <div style={{ color: "#9aa1b2", marginBottom: 4 }}>
        {Number.isFinite(t) ? `${t.toFixed(1)}s` : ""}
      </div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color ?? "#c8cddd" }}>
          {String(p.name ?? "")}: {fmt(p)}
        </div>
      ))}
      {enraged.size > 0 && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px solid #2c313e", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[...enraged.entries()].map(([m, c]) => (
            <span key={m} style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#c8cddd" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: c, display: "inline-block" }} />
              {m} enraged
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
