"use client";

import { useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { fmtClearTime, fmtDps } from "../../lib/format";
import { ApiState, useApi } from "../../lib/useApi";
import DataTable from "../DataTable";
import { MonsterSelect, StarsSelect, WeaponSelect } from "../FilterBar";
import { useFilterOptions } from "../useFilterOptions";
import EmptyState, { ScopeEmpty, scopeNames } from "../EmptyState";
import { useT, type TFn } from "@/lib/i18n";
import { monsterName, weaponTypeName } from "@/lib/names";

interface PartyMember {
  player: string;
  weapon: string;
  variant: string | null;
  dps: number;
}

interface HighScore {
  rank: number;
  hunt_id: number;
  date: string;
  monster: string;
  monster_id?: number | null;
  stars: number | null;
  clear_s: number | null;
  player: string;
  weapon: string;
  variant: string | null;
  dps: number;
  party: PartyMember[];
}

const columnsFor = (t: TFn): ColumnDef<HighScore>[] => [
  { id: "rank", accessorKey: "rank", header: "#", enableSorting: false, meta: { cls: "num" } },
  {
    id: "monster",
    accessorFn: (r) => r.monster,
    header: t("highscores.col.monster"),
    cell: ({ row }) => (
      <>{monsterName(row.original.monster, row.original.monster_id)}{" "}
        <span className="num" title={t("highscores.huntTitle", { id: row.original.hunt_id })}>#{row.original.hunt_id}</span>
      </>
    ),
  },
  {
    id: "stars",
    accessorFn: (r) => r.stars ?? -1,
    header: "★",
    meta: { cls: "num" },
    cell: ({ row }) => (row.original.stars ?? "—"),
  },
  {
    id: "clear_s",
    accessorFn: (r) => r.clear_s ?? -1,
    header: t("highscores.col.clear"),
    meta: { cls: "num" },
    cell: ({ row }) => fmtClearTime(row.original.clear_s),
  },
  { id: "date", accessorKey: "date", header: t("highscores.col.date") },
  { id: "player", accessorKey: "player", header: t("highscores.col.player") },
  {
    id: "weapon",
    accessorFn: (r) => r.variant ?? r.weapon,
    header: t("highscores.col.weapon"),
    cell: ({ row }) => (
      <>{weaponTypeName(row.original.weapon)}
        {row.original.variant ? ` · ${row.original.variant}` : ""}
      </>
    ),
  },
  {
    id: "dps",
    accessorKey: "dps",
    header: "DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.dps),
  },
  {
    id: "party",
    accessorFn: (r) => r.party.length,
    header: t("highscores.col.party"),
    enableSorting: false,
    cell: ({ row }) => (
      row.original.party.length === 0 ? t("highscores.solo") : row.original.party.map((m) => (
        <span key={m.player} className="party">
          {m.player} ({weaponTypeName(m.weapon)}{m.variant ? ` · ${m.variant}` : ""}) {fmtDps(m.dps)}
        </span>
      ))
    ),
  },
];

export default function HighScoreView({ scope, variantId, weaponName, clearScope, partySize, includeFailed }: { scope: number[]; variantId: number | string | null; weaponName: string | null; clearScope: () => void; partySize: number | null; includeFailed: boolean }) {
  const { t } = useT();
  const opts = useFilterOptions();
  const [monster, setMonster] = useState("");
  const [weapon, setWeapon] = useState("");
  const [stars, setStars] = useState("");
  const [sortBy, setSortBy] = useState<"time" | "dps">("dps");
  const [topN, setTopN] = useState("10");
  const { data, error, loading } = useApi<{ scores: HighScore[] }>("/high-scores", {
    ...(scope.length > 0 && { player_ids: scope.join(",") }),
    ...(variantId !== null && { variant_id: variantId }),
    ...(monster && { monster_id: Number(monster) }),
    ...(weapon && { weapon_id: Number(weapon) }),
    ...(weaponName && { weapon_name: weaponName }),
    ...(stars && { stars: Number(stars) }),
    sort_by: sortBy,
    ...(topN && { limit: Number(topN) }),
    ...(partySize != null && { players: partySize }),
    ...(includeFailed && { include_failed: true }),
  });
  const rows = data?.scores ?? null;

  const filters = (
    <div className="filters">
      <MonsterSelect value={monster} opts={opts}
        onChange={(v) => { setMonster(v); setStars(""); }} />
      <WeaponSelect value={weapon} onChange={setWeapon} opts={opts} />
      <StarsSelect value={stars} onChange={setStars} monster={monster} opts={opts} />
      <label>{t("highscores.filter.top")}
        <select value={topN} onChange={(e) => setTopN(e.target.value)}>
          <option value="3">3</option>
          <option value="5">5</option>
          <option value="10">10</option>
          <option value="25">25</option>
          <option value="">{t("common.all")}</option>
        </select>
      </label>
      <div className="seg" role="group" aria-label={t("highscores.sort.aria")}>
        <button type="button" className={sortBy === "time" ? "on" : ""}
          aria-pressed={sortBy === "time"}
          onClick={() => setSortBy("time")}>{t("highscores.sort.fastest")}</button>
        <button type="button" className={sortBy === "dps" ? "on" : ""}
          aria-pressed={sortBy === "dps"}
          onClick={() => setSortBy("dps")}>{t("highscores.sort.dps")}</button>
      </div>
    </div>
  );

  if (error || loading || !rows) {
    return (
      <div className="card">
        {filters}
        <ApiState error={error} loading={loading} />
      </div>
    );
  }

  if (rows.length === 0) {
    if (scope.length > 0) {
      return (
        <div className="card">
          {filters}
          <ScopeEmpty names={scopeNames(scope, opts?.players)} onClear={clearScope}>
            <p>{t("highscores.empty.scope")}</p>
          </ScopeEmpty>
        </div>
      );
    }
    return (
      <div className="card">
        {filters}
        <EmptyState what={t("highscores.empty.what")}>
          <p>{t("highscores.empty.none")}</p>
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="card">
      {filters}
      <h2>{t(sortBy === "dps" ? "highscores.heading.dps" : "highscores.heading.time", {
        count: topN || rows.length,
        rows: rows.length,
        scoped: scope.length > 0 ? t("highscores.scoped") : "",
      })}</h2>
      <DataTable
        data={rows}
        columns={columnsFor(t)}
        getRowId={(r) => `${r.hunt_id}-${r.player}`}
      />
    </div>
  );
}
