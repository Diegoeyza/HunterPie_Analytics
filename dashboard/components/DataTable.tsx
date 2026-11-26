"use client";

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { useT } from "@/lib/i18n";

interface Props<T> {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  /** Initial sort, e.g. [{ id: "dps", desc: true }]. */
  initialSort?: SortingState;
  /** Row key. Defaults to JSON.stringify (fine for small pages). */
  getRowId?: (row: T, index: number) => string;
  pageSize?: number;
  /** Optional row click (e.g. expandable detail). */
  onRowClick?: (row: T) => void;
  /** Highlights a row (e.g. the selected one); receives the row. */
  isSelected?: (row: T) => boolean;
}

const PAGE_OPTIONS = [25, 50, 100];

/** Column class convention: meta: { cls: "num" } right-aligns. */
const clsOf = (c: { columnDef: { meta?: unknown } }) =>
  (c.columnDef.meta as { cls?: string } | undefined)?.cls;

/** Shared sortable, paginated table. Headers toggle asc → desc;
 *  numeric-aware sorting comes from per-column accessorFns. */
export default function DataTable<T>({
  data,
  columns,
  initialSort = [],
  getRowId,
  pageSize = 25,
  onRowClick,
  isSelected,
}: Props<T>) {
  const { t } = useT();
  const [sorting, setSorting] = useState<SortingState>(initialSort);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize });

  const table = useReactTable({
    data,
    columns,
    state: { sorting, pagination },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    ...(getRowId ? { getRowId } : {}),
  });

  const pageCount = table.getPageCount();

  return (
    <>
      <div className="table-wrap">
        <table className="grid">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    className={clsOf(h.column)}
                    onClick={h.column.getToggleSortingHandler()}
                    title={h.column.getCanSort() ? t("table.sort.title") : undefined}
                    aria-sort={
                      h.column.getIsSorted() === "asc"
                        ? "ascending"
                        : h.column.getIsSorted() === "desc"
                        ? "descending"
                        : undefined
                    }
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    <span className="sort-ind">
                      {h.column.getIsSorted() === "asc"
                        ? "▲"
                        : h.column.getIsSorted() === "desc"
                        ? "▼"
                        : ""}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                className={[
                  onRowClick ? "clickable" : "",
                  isSelected?.(row.original) ? "selected" : "",
                ].filter(Boolean).join(" ") || undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={clsOf(cell.column)}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.length > PAGE_OPTIONS[0] && (
        <div className="pager">
          <button
            type="button"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            {t("table.pager.prev")}
          </button>
          <span>
            {t("table.pager.status", {
              page: table.getState().pagination.pageIndex + 1,
              pages: pageCount,
              rows: data.length,
            })}
          </span>
          <button
            type="button"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            {t("table.pager.next")}
          </button>
          <label>{t("table.pager.rows")}
            <select
              value={table.getState().pagination.pageSize}
              onChange={(e) => table.setPageSize(Number(e.target.value))}
            >
              {PAGE_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
              <option value={data.length}>{t("common.all")}</option>
            </select>
          </label>
        </div>
      )}
    </>
  );
}
