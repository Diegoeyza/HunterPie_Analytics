"use client";

import { useEffect, useId, useRef, useState } from "react";

export interface ComboOption {
  value: string;
  label: string;
}

/** Max rows rendered in the dropdown; beyond that show a refine hint. */
const RENDER_CAP = 100;

interface Props {
  label: string;
  value: string;
  options: ComboOption[];
  placeholder?: string;
  onChange: (value: string) => void;
}

/** Searchable combobox: substring filter, keyboard navigable, safe with
 *  thousands of options (renders at most RENDER_CAP rows). Empty value = All. */
export default function SearchSelect({ label, value, options, placeholder, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const selected = options.find((o) => o.value === value);
  const q = query.trim().toLowerCase();
  const matches = q
    ? options.filter((o) => o.label.toLowerCase().includes(q))
    : options;
  const capped = q && matches.length === 0 ? [] : matches.slice(0, RENDER_CAP);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open ]);

  useEffect(() => setHighlight(-1), [query, value]);

  const commit = (v: string) => {
    onChange(v);
    setOpen(false);
    setQuery("");
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      else setHighlight((h) => Math.min(capped.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(-1, h - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
      } else if (highlight === -1) {
        commit("");
      } else {
        const pick = capped[highlight];
        if (pick) commit(pick.value);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  };

  return (
    <label>{label}
      <div className="combo" ref={rootRef}>
        <input
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          placeholder={placeholder ?? "All — type to search"}
          value={open ? query : (selected?.label ?? "")}
          onFocus={() => { setOpen(true); setQuery(""); }}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onKeyDown={onKey}
        />
        {open && (
          <ul className="combo-list" id={listId} role="listbox">
            <li
              role="option"
              aria-selected={value === ""}
              onMouseDown={(e) => { e.preventDefault(); commit(""); }}
              onMouseEnter={() => setHighlight(-1)}
            >
              All
            </li>
            {capped.map((o, i) => (
              <li
                key={o.value}
                role="option"
                aria-selected={i === highlight || o.value === value}
                onMouseDown={(e) => { e.preventDefault(); commit(o.value); }}
                onMouseEnter={() => setHighlight(i)}
              >
                {o.label}
              </li>
            ))}
            {matches.length > RENDER_CAP && (
              <li className="combo-count" aria-hidden="true">
                {matches.length} matches — keep typing to narrow
              </li>
            )}
            {q && matches.length === 0 && (
              <li className="combo-count" aria-hidden="true">no matches</li>
            )}
          </ul>
        )}
      </div>
    </label>
  );
}
