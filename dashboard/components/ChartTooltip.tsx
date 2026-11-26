import { fmtInt, fmtPct, fmtTime } from "../lib/format";
import { useT } from "@/lib/i18n";
import { monsterName } from "@/lib/names";
import type { Metric } from "../lib/metrics";

export interface ChartEvent {
  type: string; start: number; end: number | null;
  monster?: string | null;
  /** Game monster id, so enrage badges can be localized. */
  monster_id?: number | null;
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
  const { t } = useT();
  if (!active || !payload || payload.length === 0) return null;
  const time = typeof label === "number" ? label : Number(label);
  const enraged = new Map<string, { label: string; color: string }>();
  if (Number.isFinite(time)) {
    for (const e of events) {
      if (e.type !== "enrage") continue;
      if (time >= e.start - 1e-9 && (e.end == null || time <= e.end + 1e-9)) {
        const key = String(e.monster_id ?? e.monster ?? "");
        if (key && !enraged.has(key)) {
          enraged.set(key, {
            label: monsterName(e.monster, e.monster_id),
            color: colorOf(e),
          });
        }
      }
    }
  }
  const fmt = (p: TooltipEntry) => {
    const name = String(p.name ?? "");
    if (name.includes(" HP") && typeof p.value === "number")
      return fmtPct(p.value, 1);
    if (typeof p.value !== "number") return String(p.value ?? "");
    return metric === "damage"
      ? fmtInt(p.value)
      : `${p.value.toFixed(1)} DPS`;
  };
  return (
    <div style={{ background: "#1d2029", border: "1px solid #2c313e", padding: "8px 10px", fontSize: 12 }}>
      <div style={{ color: "#9aa1b2", marginBottom: 4 }}>
        {Number.isFinite(time) ? fmtTime(time) : ""}
      </div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color ?? "#c8cddd" }}>
          {String(p.name ?? "")}: {fmt(p)}
        </div>
      ))}
      {enraged.size > 0 && (
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px solid #2c313e", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[...enraged.entries()].map(([key, e]) => (
            <span key={key} style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#c8cddd" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: e.color, display: "inline-block" }} />
              {t("table.chart.enraged", { monster: e.label })}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
