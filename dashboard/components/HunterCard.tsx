"use client";

import { fmtDps, fmtInt, fmtPct } from "../lib/format";

export interface HunterCardData {
  player: string;
  /** Right-side caption (weapon, hunt count…). */
  caption: string;
  /** Hunter rank at quest time; null/undefined hides the badge. */
  hunter_rank?: number | null;
  total_damage: number;
  dps: number | null;
  /** Share of the relevant total (hunt team or quest), 0..1. */
  share: number;
  /** Denominator label, e.g. "of hunt" / "of quest · 3 hunts". */
  shareLabel: string;
}

/** Party-member stat card: name + caption, big damage, DPS + share, bar.
 *  Shared by the Quests and Hunts popups. */
export default function HunterCard({ m, mvp }: { m: HunterCardData; mvp: boolean }) {
  const nameTitle = m.hunter_rank != null
    ? `${m.player} · Hunter Rank ${m.hunter_rank}`
    : m.player;
  return (
    <div className={`member-card${mvp ? " mvp" : ""}`}>
      <div className="member-top">
        <span className="member-name" title={nameTitle}>
          <span className="member-name-text">{mvp ? "★ " : ""}{m.player}</span>
          {m.hunter_rank != null && (
            <span className="member-hr">HR {m.hunter_rank}</span>
          )}
        </span>
        <span className="muted" title={m.caption}>{m.caption}</span>
      </div>
      <div className="member-dmg">{fmtInt(m.total_damage)}</div>
      <div className="member-sub">
        <span>{fmtDps(m.dps)} DPS</span>
        <span className="muted">{fmtPct(m.share, 1)} {m.shareLabel}</span>
      </div>
      <div className="share-track">
        <div className="share-fill" style={{ width: `${Math.max(1.5, m.share * 100)}%` }} />
      </div>
    </div>
  );
}
