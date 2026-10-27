"use client";

import { useId, useState, type ReactNode } from "react";

/** Foldable section for long detail views (hunt popup: chart, survival,
 *  highlights). The header is a real button, so Enter/Space and screen
 *  readers work without extra key handling; the body unmounts while closed
 *  (a collapsed chart stops rendering instead of hiding behind CSS). */
export default function Collapsible({
  title, subtitle, defaultOpen = true, children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  return (
    <section className={`collapsible${open ? " open" : ""}`}>
      <button
        type="button"
        className="collapsible-head"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="collapsible-arrow" aria-hidden="true">▾</span>
        <span className="collapsible-title">{title}</span>
        {subtitle && <span className="collapsible-sub">{subtitle}</span>}
      </button>
      {open && <div className="collapsible-body" id={bodyId}>{children}</div>}
    </section>
  );
}
