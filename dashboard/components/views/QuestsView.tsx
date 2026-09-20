"use client";

import { useEffect, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { createPortal } from "react-dom";
import { apiGet } from "../../lib/api";
import { fmtDps, fmtPct, fmtTime } from "../../lib/format";
import DataTable from "../DataTable";
import EmptyState from "../EmptyState";
import HunterCard, { fmtDmg } from "../HunterCard";

interface QuestRow {
  /** Stable group key (hunt:<id> | survey:<qid>:<mid> | quest:<qid>). */
  key: string;
  quest_id: number | null; monster: string; stars: number | null;
  max_hp: number | null; hunts: number; carts: number; clear_rate: number;
  avg_clear_s: number | null;
  best_clear: { hunt_id: number; clear_s: number } | null;
  best_dps: number; enrage_uptime: number;
}

interface QuestMember {
  player: string; weapon: string;
  total_damage: number; dps: number | null;
}

interface QuestInstance {
  id: number; started_at: string;
  clear_s: number | null; cleared: boolean; carts: number;
  members: QuestMember[];
}

const columns: ColumnDef<QuestRow>[] = [
  {
    id: "quest", accessorFn: (r) => r.quest_id ?? -1, header: "Quest",
    cell: ({ row }) => (row.original.quest_id === null ? "—" : `#${row.original.quest_id}`),
  },
  { id: "monster", accessorKey: "monster", header: "Monster" },
  {
    id: "stars", accessorFn: (r) => r.stars ?? -1, header: "★",
    meta: { cls: "num" },
    cell: ({ row }) => (row.original.stars ?? "—"),
  },
  {
    id: "max_hp", accessorFn: (r) => r.max_hp ?? -1, header: "HP",
    meta: { cls: "num" },
    cell: ({ row }) => (row.original.max_hp ? Math.round(row.original.max_hp).toLocaleString() : "—"),
  },
  { id: "hunts", accessorKey: "hunts", header: "Hunts", meta: { cls: "num" } },
  {
    id: "clear_rate", accessorKey: "clear_rate", header: "Clear %",
    meta: { cls: "num" },
    cell: ({ row }) => fmtPct(row.original.clear_rate),
  },
  {
    id: "avg_clear_s", accessorFn: (r) => r.avg_clear_s ?? -1, header: "Avg clear",
    meta: { cls: "num" },
    cell: ({ row }) => fmtTime(row.original.avg_clear_s),
  },
  {
    id: "best_clear", accessorFn: (r) => r.best_clear?.clear_s ?? -1, header: "Best clear",
    meta: { cls: "num" },
    cell: ({ row }) => (
      row.original.best_clear
        ? `#${row.original.best_clear.hunt_id} ${fmtTime(row.original.best_clear.clear_s)}`
        : "—"
    ),
  },
  {
    id: "best_dps", accessorKey: "best_dps", header: "Best DPS",
    meta: { cls: "num" },
    cell: ({ row }) => fmtDps(row.original.best_dps),
  },
  {
    id: "enrage_uptime", accessorKey: "enrage_uptime", header: "Enrage %",
    meta: { cls: "num" },
    cell: ({ row }) => fmtPct(row.original.enrage_uptime),
  },
  { id: "carts", accessorKey: "carts", header: "Carts", meta: { cls: "num" } },
];

/** Popup for the clicked quest: its summary stats plus each run as its own
 *  expandable instance with that run's hunter damage + DPS. Latest run
 *  starts expanded. Closes on backdrop click, the × button, or Escape. */
function QuestPopup({ quest, onClose, partySize }: { quest: QuestRow; onClose: () => void; partySize: number | null }) {
  const [instances, setInstances] = useState<QuestInstance[] | null>(null);
  const [open, setOpen] = useState<Set<number>>(new Set());

  useEffect(() => {
    setInstances(null);
    setOpen(new Set());
    apiGet<{ hunts: QuestInstance[] }>("/quests/detail", {
      key: quest.key,
      ...(partySize != null && { players: partySize }),
    }).then(
      (d) => {
        // ?? []: a stale API serving the previous response shape must show
        // an empty list, never crash the whole tab (instances.map below).
        const hunts = d.hunts ?? [];
        setInstances(hunts);
        if (hunts.length > 0) setOpen(new Set([hunts[0].id]));
      },
      () => setInstances([]),
    );
  }, [quest.key, partySize]);

  const toggle = (id: number) =>
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const title =
    `${quest.quest_id === null ? "Hunt" : `#${quest.quest_id}`} ${quest.monster}` +
    `${quest.stars ? ` ${quest.stars}★` : ""}`;
  const stats: [string, string][] = [
    ["Hunts", String(quest.hunts)],
    ["Clear rate", fmtPct(quest.clear_rate)],
    ["Avg clear", fmtTime(quest.avg_clear_s)],
    ["Best clear", quest.best_clear
      ? `#${quest.best_clear.hunt_id} ${fmtTime(quest.best_clear.clear_s)}` : "—"],
    ["Best DPS", fmtDps(quest.best_dps)],
    ["Enrage", fmtPct(quest.enrage_uptime)],
    ["Carts", String(quest.carts)],
  ];
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel" role="dialog" aria-modal="true" aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="modal-body">
          <div className="quest-stats">
            {stats.map(([label, value]) => (
              <div className="quest-stat" key={label}>
                <span className="muted">{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {instances === null ? (
            <p>Loading hunts…</p>
          ) : (
            <div className="quest-instances">
              {instances.map((h) => {
                const team = h.members.reduce((s, m) => s + m.total_damage, 0);
                const isOpen = open.has(h.id);
                return (
                  <div className="quest-instance" key={h.id}>
                    <button
                      type="button"
                      className="quest-instance-head"
                      aria-expanded={isOpen}
                      onClick={() => toggle(h.id)}
                    >
                      <span className="quest-instance-toggle">{isOpen ? "▾" : "▸"}</span>
                      <strong>#{h.id}</strong>
                      <span className="muted">
                        {h.started_at.slice(0, 10)}
                        {h.clear_s ? ` · ${h.cleared ? "cleared" : "failed"} in ${fmtTime(h.clear_s)}` : ""}
                        {h.carts > 0 ? ` · ${h.carts} cart${h.carts === 1 ? "" : "s"}` : ""}
                        {` · ${fmtDmg(team)} team damage · ${h.members.length} hunter${h.members.length === 1 ? "" : "s"}`}
                      </span>
                    </button>
                    {isOpen && (
                      <div className="member-grid">
                        {h.members.map((m, i) => (
                          <HunterCard
                            key={m.player}
                            m={{
                              player: m.player, caption: m.weapon,
                              total_damage: m.total_damage, dps: m.dps,
                              share: team > 0 ? m.total_damage / team : 0,
                              shareLabel: "of hunt",
                            }}
                            mvp={i === 0 && h.members.length > 1}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

export default function QuestsView({ partySize }: { partySize: number | null }) {
  const [rows, setRows] = useState<QuestRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<QuestRow | null>(null);

  useEffect(() => {
    apiGet<{ quests: QuestRow[] }>("/quests", {
      ...(partySize != null && { players: partySize }),
    })
      .then((d) => setRows(d.quests))
      .catch((e: Error) => setError(e.message));
  }, [partySize]);

  if (error) return <p className="error">{error} — is the API running?</p>;
  if (!rows) return <p>Loading…</p>;
  if (rows.length === 0) {
    return (
      <EmptyState what="quest data">
        <p>Import hunts first — quests appear once dumps carry quest ids.</p>
      </EmptyState>
    );
  }

  return (
    <div className="card">
      <h2>Quests ({rows.length}) — same monster, different HP per quest. Click a row for hunter DPS.</h2>
      <DataTable
        data={rows}
        columns={columns}
        initialSort={[{ id: "hunts", desc: true }]}
        getRowId={(r, i) => `${r.key}-${i}`}
        onRowClick={setSelected}
        isSelected={(r) => r.key === selected?.key}
      />
      {selected && <QuestPopup quest={selected} onClose={() => setSelected(null)} partySize={partySize} />}
    </div>
  );
}
