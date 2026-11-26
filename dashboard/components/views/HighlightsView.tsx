"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import { AwardMultiSelect, MonsterSelect, StarsSelect, WeaponSelect } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState from "../EmptyState";
import { fmtAward } from "../../lib/format";
import { t as tr, useT } from "@/lib/i18n";
import { awardName } from "@/lib/names";
import type { Highlights, HighlightLeader, DamageShareRow } from "../../lib/api";

const makeLeaderColumns = (unit: number, t: typeof tr): ColumnDef<HighlightLeader>[] => [
  { id: "player", accessorKey: "player", header: t("highlights.player") },
  {
    id: "total", accessorKey: "total", header: t("highlights.total"), meta: { cls: "num" },
    cell: ({ row }) => fmtAward(row.original.total, unit),
  },
  {
    id: "best", accessorKey: "best", header: t("highlights.best"), meta: { cls: "num" },
    cell: ({ row }) => fmtAward(row.original.best, unit),
  },
  { id: "hunts", accessorKey: "hunts", header: t("highlights.hunts"), meta: { cls: "num" } },
];

const makeShareColumns = (t: typeof tr): ColumnDef<DamageShareRow>[] => [
  { id: "player", accessorKey: "player", header: t("highlights.player") },
  {
    id: "avg_share", accessorKey: "avg_share", header: t("highlights.avgShare"),
    meta: { cls: "num" }, cell: ({ row }) => `${(row.original.avg_share * 100).toFixed(1)}%`,
  },
  { id: "hunts", accessorKey: "hunts", header: t("highlights.hunts"), meta: { cls: "num" } },
];

/** All-highlights leader: best single run, not the lifetime sum. Ties fall
 *  back to the higher total, then the name, so the row is deterministic. */
function topByBest(leaders: HighlightLeader[]): HighlightLeader | null {
  return leaders.reduce<HighlightLeader | null>((top, r) => {
    if (!top) return r;
    if (r.best !== top.best) return r.best > top.best ? r : top;
    if (r.total !== top.total) return r.total > top.total ? r : top;
    return r.player.localeCompare(top.player) < 0 ? r : top;
  }, null);
}

export default function HighlightsView({ scope, weaponName, partySize, includeFailed }: { scope: number[]; weaponName: string | null; partySize: number | null; includeFailed: boolean }) {
  const { t } = useT();
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [stars, setStars] = useState("");
  const [awardId, setAwardId] = useState<string>("");
  // Which highlights to show (award ids); default = all that have data.
  const [selectedAwards, setSelectedAwards] = useState<number[]>([]);

  const { data, error, loading } = useApi<Highlights>("/highlights", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(monster && { monster_id: Number(monster) }),
    ...(stars && { stars: Number(stars) }),
    ...(weapon && { weapon_id: Number(weapon) }),
    ...(weaponName && { weapon_name: weaponName }),
    ...(partySize != null && { players: partySize }),
    ...(includeFailed && { include_failed: true }),
  });

  const awards = data?.awards ?? [];
  // Keep the visible-selection in sync with what the server returned.
  useEffect(() => {
    const allIds = awards.map((a) => a.id);
    if (allIds.length === 0) return;
    setSelectedAwards((prev) => {
      const kept = prev.filter((id) => allIds.includes(id));
      return kept.length ? kept : allIds;
    });
  }, [awards]);
  const visibleAwards = awards.filter((a) => selectedAwards.includes(a.id));

  // Default to a meaningful award: the one with the most data, else damage.
  useEffect(() => {
    if (visibleAwards.length === 0) return;
    if (awardId && visibleAwards.some((a) => String(a.id) === awardId)) return;
    const byDamage = visibleAwards.find((a) => a.id === 4);
    const best = visibleAwards.reduce((a, b) =>
      b.leaders.length > a.leaders.length ? b : a, visibleAwards[0]);
    setAwardId(String((byDamage ?? best).id));
  }, [visibleAwards, awardId]);

  const filters = (
    <div className="filters">
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      {awards.length > 0 && (
        <AwardMultiSelect options={awards} value={selectedAwards}
          onChange={setSelectedAwards} />
      )}
    </div>
  );

  if (error || loading || !data) {
    return (
      <div className="card">
        {filters}
        <ApiState error={error} loading={loading} />
      </div>
    );
  }

  if (awards.length === 0 && data.damage_share.length === 0) {
    return (
      <div className="card">
        {filters}
        <EmptyState what={t("highlights.empty.what")}>
          <p>{t("highlights.empty.note")}</p>
        </EmptyState>
      </div>
    );
  }

  const selected = visibleAwards.find((a) => String(a.id) === awardId)
    ?? visibleAwards[0] ?? null;
  // Plain value, not useMemo: it must not be a hook called after the early
  // returns above (that changed the hook order once data loaded).
  const leaderColumns = makeLeaderColumns(selected?.unit ?? 2, t);
  const shareColumns = makeShareColumns(t);

  return (
    <div className="cards-2">
      <div className="card">
        {filters}
        <h2>{t("highlights.leaderboard")}</h2>
        {awards.length === 0 ? (
          <p className="blurb">{t("highlights.noAwards")}</p>
        ) : visibleAwards.length === 0 ? (
          <p className="blurb">{t("highlights.noneSelected")}</p>
        ) : (
          <>
            <div className="filters">
              <label>{t("highlights.award")}
                <select value={awardId} onChange={(e) => setAwardId(e.target.value)}>
                  {visibleAwards.map((a) => (
                    <option key={a.id} value={a.id}>{awardName(a.id, a.name)}</option>
                  ))}
                </select>
              </label>
            </div>
            {selected?.explain && <p className="blurb">{selected.explain}</p>}
            {selected && (
              <DataTable
                data={selected.leaders}
                columns={leaderColumns}
                initialSort={[{ id: "total", desc: true }]}
                getRowId={(r) => String(r.player_id)}
              />
            )}
          </>
        )}
      </div>
      <div className="card">
        <h2>{t("highlights.shareTitle")}</h2>
        {data.damage_share.length === 0 ? (
          <p className="blurb">{t("highlights.noDamage")}</p>
        ) : (
          <DataTable
            data={data.damage_share}
            columns={shareColumns}
            initialSort={[{ id: "avg_share", desc: true }]}
            getRowId={(r) => String(r.player_id)}
          />
        )}
        <h2 style={{ marginTop: 16 }}>{t("highlights.all")}</h2>
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr><th>{t("highlights.award")}</th><th>{t("highlights.topHunter")}</th><th className="num">{t("highlights.best")}</th></tr>
            </thead>
            <tbody>
              {visibleAwards.map((a) => {
                const top = topByBest(a.leaders);
                return (
                  <tr key={a.id} onClick={() => setAwardId(String(a.id))}
                    style={{ cursor: "pointer" }}>
                    <td>{awardName(a.id, a.name)}</td>
                    <td>{top?.player ?? "—"}</td>
                    <td className="num">{top ? fmtAward(top.best, a.unit) : "—"}</td>
                  </tr>
                );
              })}
              {visibleAwards.length === 0 && (
                <tr><td colSpan={3} className="muted">{t("highlights.tableNone")}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
