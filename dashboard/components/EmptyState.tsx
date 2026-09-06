import type { ReactNode } from "react";

export default function EmptyState({ what, children }: { what: string; children: ReactNode }) {
  return (
    <div className="empty">
      <p>No {what} yet.</p>
      <div>{children}</div>
    </div>
  );
}
