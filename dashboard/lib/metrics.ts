/** Shared chart metric math (Damage curves tab + Hunts popup chart).
 *  Kept in one place so both views compute identical series. */

export type Metric = "damage" | "dps" | "burst" | "burst1";

type DamagePoint = { t: number; dmg: number };

const SMOOTH_WINDOW = 5;

/** Compute DPS from cumulative damage, starting at each player's first hit.
 *  The series is a live trace — damage-so-far over (now - first hit) — like
 *  the in-game meter. When the player stops hitting before the quest ends,
 *  one decaying point is appended at the quest end so the curve lands on
 *  the same final DPS the headlines show (total / (quest end - first hit)),
 *  matching the meter's frozen results value. */
export function computeDps(points: { t: number; dmg: number }[], endT: number): { t: number; dps: number }[] {
  if (points.length === 0) return [];
  // DPS is measured over engagement time (first hit -> now), the same on every
  // tab. A series may start with an anchoring (0, 0) point so cumulative
  // charts begin at quest start: skip zero-damage points when finding the
  // first hit, otherwise the denominator would include the run to the monster.
  const anchored = points.length > 1 && points[0].t === 0 && points[0].dmg === 0;
  let first = 0;
  while (first < points.length - 1 && points[first].dmg <= 0) first++;
  const firstHit = points[first].t;
  // A late-attached companion's first sample carries all damage dealt so far
  // (observed 10.8k in one frame): subtract it so attach is not a fake spike.
  const lastDmg = points[points.length - 1].dmg;
  const bulk = !anchored && lastDmg > 0 && points[first].dmg > 0.25 * lastDmg;
  const baseline = bulk ? points[first].dmg : 0;
  const series = points.map((q) => {
    if (q.t <= firstHit) return { t: q.t, dps: 0 };
    const window = q.t - firstHit;
    return { t: q.t, dps: window > 0 ? Math.max(0, q.dmg - baseline) / window : 0 };
  });
  const lastP = points[points.length - 1];
  if (Number.isFinite(endT) && endT > lastP.t + 1e-9) {
    const window = endT - firstHit;
    if (window > 0) series.push({ t: endT, dps: Math.max(0, lastP.dmg - baseline) / window });
  }
  return series;
}

/** Rolling mean over a player's DPS series. */
export function smoothDps(dpsSeries: { t: number; dps: number }[]): { t: number; dps: number }[] {
  return dpsSeries.map((q, i) => {
    const seg = dpsSeries.slice(Math.max(0, i - SMOOTH_WINDOW + 1), i + 1);
    return { t: q.t, dps: seg.reduce((a, b) => a + b.dps, 0) / seg.length };
  });
}

/** Cumulative damage at an arbitrary time.
 *
 *  Damage snapshots are event-driven and have very different cadences: the
 *  local hunter is sampled several times per second, while party members are
 *  usually sampled about every 5 s. A fixed window therefore has to be
 *  evaluated against the time axis, not against the previous sample.
 *
 *  Between samples, damage is interpolated linearly (the only estimate the
 *  data supports). A leading zero-damage anchor stays flat so the synthetic
 *  quest-start point cannot smear the first real hit across the run-up. */
function cumulativeAt(points: DamagePoint[], t: number): number {
  if (points.length === 0) return 0;
  const first = points[0];
  const last = points[points.length - 1];
  if (t < first.t) return 0;
  if (t > last.t) return last.dmg;

  let lo = 0;
  let hi = points.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid].t <= t) lo = mid;
    else hi = mid;
  }
  const a = points[lo];
  const b = points[hi];
  if (t <= a.t) return a.dmg;
  if (t >= b.t) return b.dmg;
  // Damage first recorded after a zero-damage anchor is treated as a step at
  // the sample that carries it; otherwise the anchor would turn the first hit
  // into a long, flat ramp.
  if (a.dmg <= 0 && b.dmg > 0) return 0;
  const span = b.t - a.t;
  return span > 0 ? a.dmg + ((b.dmg - a.dmg) * (t - a.t)) / span : b.dmg;
}

/** DPS over the fixed window ending at `t`, independent of sample cadence. */
export function burstAt(points: DamagePoint[], t: number, window = 5): number {
  if (points.length === 0 || window <= 0 || t < points[0].t) return 0;
  const windowStart = t - window;
  const startDmg = windowStart < points[0].t ? 0 : cumulativeAt(points, windowStart);
  const endDmg = cumulativeAt(points, t);
  return Math.max(0, endDmg - startDmg) / window;
}

/** Compute instantaneous DPS over a window (default 5s) ending at each
 *  timestamp. The 1s variant shows burst damage more sharply.
 *
 *  Pass `times` to evaluate the window on a shared chart grid. That keeps a
 *  5s-sampled party member's curve aligned with the local hunter's dense
 *  samples instead of carrying one stale value forward for five seconds. */
export function computeBurst(points: DamagePoint[], window = 5,
                             times?: number[]): { t: number; dps: number }[] {
  if (points.length === 0) return [];
  const evalTimes = (times ?? points.map((p) => p.t))
    .filter((t) => t >= points[0].t - 1e-9);
  return evalTimes.map((t) => ({ t, dps: burstAt(points, t, window) }));
}
