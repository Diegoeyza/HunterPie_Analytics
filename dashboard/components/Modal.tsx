"use client";

import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Single modal system: portal + Escape + scroll-lock + labelled dialog.
 *  Replaces the two ad-hoc systems (modal-overlay/modal-panel without
 *  portal, modal-backdrop/modal without Escape handling).
 */
export default function Modal({ label, onClose, children, wide }: {
  label: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal${wide ? " wide" : ""}`} onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-label={label}>
        {children}
      </div>
    </div>,
    document.body
  );
}
