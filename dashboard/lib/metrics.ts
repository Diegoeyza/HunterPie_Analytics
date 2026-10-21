/** Shared chart metric math (Damage curves tab + Hunts popup chart).
 *  Kept in one place so both views compute identical series. */

export type Metric = "damage" | "dps" | "burst";

const SMOOTH_WINDOW = 5;

/** Compute DPS from cumulative damage, starting from each player's first hit
 *  and ending at monster death (last HP step). After death, DPS plateaus. */
export function computeDps(points: { t: number; dmg: number }[], deathT: number): { t: number; dps: number }[] {
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
  return points.map((q) => {
    if (q.t <= firstHit) return { t: q.t, dps: 0 };
    const end = Math.min(q.t, deathT);
    const window = end - firstHit;
    return { t: q.t, dps: window > 0 ? (q.dmg - baseline) / window : 0 };
  });
}

/** Rolling mean over a player's DPS series. */
export function smoothDps(dpsSeries: { t: number; dps: number }[]): { t: number; dps: number }[] {
  return dpsSeries.map((q, i) => {
    const seg = dpsSeries.slice(Math.max(0, i - SMOOTH_WINDOW + 1), i + 1);
    return { t: q.t, dps: seg.reduce((a, b) => a + b.dps, 0) / seg.length };
  });
}

/** Compute instantaneous DPS over a 5-second window ending at each timestamp. */
export function computeBurst(points: { t: number; dmg: number }[]): { t: number; dps: number }[] {
  if (points.length === 0) return [];
  const WINDOW = 5;
  return points.map((q) => {
    const windowStart = q.t - WINDOW;
    let dmgAtStart = 0;
    for (const p of points) {
      if (p.t > windowStart + 1e-9) break;
      dmgAtStart = p.dmg;
    }
    return { t: q.t, dps: (q.dmg - dmgAtStart) / WINDOW };
  });
}
