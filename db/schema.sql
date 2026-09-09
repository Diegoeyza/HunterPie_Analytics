-- HunterPie_Analytics V1 schema draft (SQLite + Postgres compatible)
-- Source: PLAN.md §4 as amended by plan review.
-- Timestamps are TIMESTAMP (SQLite stores ISO8601 text); offsets are REAL seconds.

CREATE TABLE players (
    id            INTEGER PRIMARY KEY,
    display_name  TEXT NOT NULL,
    first_seen_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_players_name ON players(display_name);

CREATE TABLE weapons (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    weapon_type TEXT NOT NULL  -- GS, LS, SnS, DB, ...
);

CREATE TABLE monsters (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    species TEXT
);

CREATE TABLE hunts (
    id                      INTEGER PRIMARY KEY,
    quest_id_external       TEXT,            -- HunterPie quest/session ID when available
    dedup_hash              TEXT UNIQUE,     -- fallback: hash(monster, players, start_ts rounded to 1s)
    monster_id              INTEGER NOT NULL REFERENCES monsters(id),
    quest_id                INTEGER,         -- HunterPie quest id (same monster, different HP per quest)
    quest_type              INTEGER,
    quest_level             INTEGER,
    quest_stars             INTEGER,         -- e.g. 6★ Xu Wu
    monster_max_hp          REAL,            -- per-hunt instance HP (varies by quest)
    monster_variant         INTEGER,
    monster_crown           INTEGER,         -- crown roll (0 = none seen yet)
    started_at              TIMESTAMP NOT NULL,
    ended_at                TIMESTAMP,
    quest_time_seconds      REAL,            -- HunterPie "quest time"
    real_hunt_time_seconds  REAL,            -- HunterPie "real hunt time" (may differ)
    cart_count              INTEGER NOT NULL DEFAULT 0,
    cleared                 BOOLEAN NOT NULL DEFAULT 0,
    ignored                 BOOLEAN NOT NULL DEFAULT 0,  -- user-hidden: excluded from all stats
    player_count            INTEGER NOT NULL DEFAULT 1,
    is_sos                  BOOLEAN NOT NULL DEFAULT 0,  -- upstream: SOS data is inaccurate
    joined_mid_hunt         BOOLEAN NOT NULL DEFAULT 0,  -- upstream: mid-join not tracked properly
    hunterpie_version       TEXT NOT NULL,   -- Phase 4 version-mismatch gating needs this stored
    game_version            TEXT NOT NULL,
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_hunts_started ON hunts(started_at);
CREATE INDEX idx_hunts_monster ON hunts(monster_id);

CREATE TABLE hunt_players (
    hunt_id       INTEGER NOT NULL REFERENCES hunts(id) ON DELETE CASCADE,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    weapon_id     INTEGER REFERENCES weapons(id),  -- nullable: Wilds may not expose per-player weapon
    total_damage  REAL NOT NULL DEFAULT 0,
    peak_dps      REAL NOT NULL DEFAULT 0,
    is_supporter  BOOLEAN NOT NULL DEFAULT 0,      -- NPC/supporter: exclude from synergy stats
    gear_raw      REAL,  -- fork gear fingerprint (local player only); NULL = pre-gear export
    gear_element  REAL,
    gear_affinity REAL,
    PRIMARY KEY (hunt_id, player_id)
);

CREATE TABLE weapon_identities (
    id            INTEGER PRIMARY KEY,
    weapon_type   TEXT NOT NULL,   -- e.g. HuntingHorn
    gear_raw      REAL NOT NULL,
    gear_element  REAL NOT NULL,
    gear_affinity REAL NOT NULL,
    label         TEXT,            -- user-assigned name, e.g. "Artian Horn III"
    UNIQUE (weapon_type, gear_raw, gear_element, gear_affinity)
);

CREATE TABLE dps_snapshots (
    id                 INTEGER PRIMARY KEY,
    hunt_id            INTEGER NOT NULL REFERENCES hunts(id) ON DELETE CASCADE,
    player_id          INTEGER NOT NULL REFERENCES players(id),
    ts_offset_seconds  REAL NOT NULL,   -- offset from quest start (REAL, not INT: 1-5s frames + moving avg)
    cumulative_damage  REAL NOT NULL DEFAULT 0,
    instant_dps        REAL NOT NULL DEFAULT 0
);
CREATE INDEX idx_snapshots_hunt_ts ON dps_snapshots(hunt_id, ts_offset_seconds);

-- Phase/enrage/abnormality spans for FR-3.3 markers.
-- HunterPie's own Hunt Export already tracks enrage + abnormality uptimes.
CREATE TABLE monster_events (
    id                   INTEGER PRIMARY KEY,
    hunt_id              INTEGER NOT NULL REFERENCES hunts(id) ON DELETE CASCADE,
    monster_id           INTEGER NOT NULL REFERENCES monsters(id),
    event_type           TEXT NOT NULL,  -- e.g. 'enrage', 'abnormality'
    start_offset_seconds REAL NOT NULL,
    end_offset_seconds   REAL
);
CREATE INDEX idx_events_hunt ON monster_events(hunt_id, monster_id);

-- Monster HP fraction over time (HunterPie health_steps) — feeds the HP
-- overlay on FR-3.3 damage curves.
CREATE TABLE monster_health_steps (
    id                 INTEGER PRIMARY KEY,
    hunt_id            INTEGER NOT NULL REFERENCES hunts(id) ON DELETE CASCADE,
    monster_id         INTEGER NOT NULL REFERENCES monsters(id),
    ts_offset_seconds  REAL NOT NULL,
    hp_fraction        REAL NOT NULL   -- 1.0 = full, 0.0 = dead
);
CREATE INDEX idx_hpsteps_hunt_ts ON monster_health_steps(hunt_id, ts_offset_seconds);

-- Pinned hunters (own hunters): star them once, scope views to them.
CREATE TABLE player_pins (
    player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
    pinned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
