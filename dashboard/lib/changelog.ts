/** Release notes for the in-app "What's new" popup.
 *
 *  Kept in the bundle (not fetched) so the popup works offline and when the
 *  update check is off; it links to GitHub for the full notes. Add one entry
 *  per release worth announcing — the popup opens once per version, the first
 *  time the app runs it (Settings → Data also re-opens it on demand).
 *
 *  `title` and `bullets` hold translation keys (area `changelog.<version>`);
 *  the caller translates them so this file stays pure data. */

import type { MessageKey } from "../locales/en";

export type ReleaseNote = {
  version: string;
  title: MessageKey;
  bullets: MessageKey[];
};

export const RELEASES_URL = "https://github.com/Diegoeyza/HunterPie_Analytics/releases";

export const RELEASES: ReleaseNote[] = [
  {
    version: "1.3.0",
    title: "changelog.1.3.0.title",
    bullets: [
      "changelog.1.3.0.0",
      "changelog.1.3.0.1",
      "changelog.1.3.0.2",
    ],
  },
  {
    version: "1.2.6",
    title: "changelog.1.2.6.title",
    bullets: [
      "changelog.1.2.6.0",
      "changelog.1.2.6.1",
      "changelog.1.2.6.2",
      "changelog.1.2.6.3",
    ],
  },
  {
    version: "1.2.5",
    title: "changelog.1.2.5.title",
    bullets: [
      "changelog.1.2.5.0",
      "changelog.1.2.5.1",
    ],
  },
  {
    version: "1.2.4",
    title: "changelog.1.2.4.title",
    bullets: [
      "changelog.1.2.4.0",
      "changelog.1.2.4.1",
      "changelog.1.2.4.2",
      "changelog.1.2.4.3",
    ],
  },
];

/** The note for a given app version, if one was written. */
export function noteFor(version?: string | null): ReleaseNote | null {
  if (!version) return null;
  return RELEASES.find((r) => r.version === version) ?? null;
}

const SEEN_KEY = "hp.seenVersion";

/** Last app version whose note was acknowledged (null = never). */
export function loadSeenVersion(): string | null {
  try {
    return localStorage.getItem(SEEN_KEY);
  } catch {
    return null;
  }
}

export function storeSeenVersion(version: string): void {
  try {
    localStorage.setItem(SEEN_KEY, version);
  } catch { /* private mode: the popup just shows again next time */ }
}
