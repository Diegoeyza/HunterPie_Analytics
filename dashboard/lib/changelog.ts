/** Release notes for the in-app "What's new" popup.
 *
 *  Kept in the bundle (not fetched) so the popup works offline and when the
 *  update check is off; it links to GitHub for the full notes. Add one entry
 *  per release worth announcing — the popup opens once per version, the first
 *  time the app runs it (Settings → Data also re-opens it on demand). */

export type ReleaseNote = {
  version: string;
  title: string;
  bullets: string[];
};

export const RELEASES_URL = "https://github.com/Diegoeyza/HunterPie_Analytics/releases";

export const RELEASES: ReleaseNote[] = [
  {
    version: "1.2.5",
    title: "Fixes",
    bullets: [
      "The \u201cWhat's new\u201d note now stays closed after you close it. It used to come back on every launch because the desktop app picked a new local port each time, which reset the browser storage that remembered it.",
      "The app now keeps a stable local port, so your last tab, hunter scope, filters and party size are remembered across launches too.",
    ],
  },
  {
    version: "1.2.4",
    title: "Only quest objectives",
    bullets: [
      "Hunts for a monster that only invaded the quest — a Guardian Rathalos in an Arkveld quest, for example — are now hidden automatically, exactly like pressing Ignore.",
      "Settings → Data → \u201cOnly quest objectives\u201d turns it on or off. Older hunts are re-read from your export files, so the filter covers past quests too.",
      "Ignores you made yourself are always kept. Turning the filter off restores only the hunts it hid. No mod update needed.",
      "Hunts → All hunts now has Delete as well as Ignore: Delete removes a hunt from every stat and from the list for good (a re-import won't bring it back), and \u201cShow deleted\u201d lets you restore one.",
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
