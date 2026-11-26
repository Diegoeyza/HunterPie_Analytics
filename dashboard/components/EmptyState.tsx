import type { ReactNode } from "react";
import { useT } from "@/lib/i18n";

export default function EmptyState({ what, children }: { what: string; children: ReactNode }) {
  const { t } = useT();
  return (
    <div className="empty">
      <p>{t("table.empty.none", { what })}</p>
      <div>{children}</div>
    </div>
  );
}

/** Map scoped ids to display names (falls back to #id). */
export function scopeNames(scope: number[], players?: { id: number; name: string }[]): string[] {
  return scope.map((id) => players?.find((p) => p.id === id)?.name ?? `#${id}`);
}

/** Empty state for scope-filtered views: names who's excluded and offers
 *  a one-click escape hatch instead of the misleading "import hunts" hint. */
export function ScopeEmpty({ names, onClear, children }: {
  names: string[]; onClear: () => void; children?: ReactNode;
}) {
  const { t } = useT();
  return (
    <div className="empty">
      <p>{t("table.empty.scope", { names: names.join(" + ") })}</p>
      <div>
        {children}
        <p><button type="button" onClick={onClear}>{t("table.empty.clearScope")}</button></p>
      </div>
    </div>
  );
}
