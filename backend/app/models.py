"""SQLAlchemy models — mirrors db/schema.sql (source of truth for V1)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("idx_players_name", "display_name"),)


class Weapon(Base):
    __tablename__ = "weapons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    weapon_type: Mapped[str] = mapped_column(Text, nullable=False)


class Monster(Base):
    __tablename__ = "monsters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    species: Mapped[str | None] = mapped_column(Text)


class Hunt(Base):
    __tablename__ = "hunts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quest_id_external: Mapped[str | None] = mapped_column(String(128))
    dedup_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    monster_id: Mapped[int] = mapped_column(ForeignKey("monsters.id"), nullable=False)
    quest_id: Mapped[int | None] = mapped_column(Integer)
    quest_type: Mapped[int | None] = mapped_column(Integer)
    quest_level: Mapped[int | None] = mapped_column(Integer)
    quest_stars: Mapped[int | None] = mapped_column(Integer)
    monster_max_hp: Mapped[float | None] = mapped_column(Float)
    monster_variant: Mapped[int | None] = mapped_column(Integer)
    monster_crown: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    quest_time_seconds: Mapped[float | None] = mapped_column(Float)
    real_hunt_time_seconds: Mapped[float | None] = mapped_column(Float)
    cart_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    player_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_sos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    joined_mid_hunt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hunterpie_version: Mapped[str] = mapped_column(Text, nullable=False)
    game_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    monster: Mapped[Monster] = relationship()

    __table_args__ = (
        Index("idx_hunts_started", "started_at"),
        Index("idx_hunts_monster", "monster_id"),
    )


class HuntPlayer(Base):
    __tablename__ = "hunt_players"

    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id", ondelete="CASCADE"), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    weapon_id: Mapped[int | None] = mapped_column(ForeignKey("weapons.id"))
    total_damage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    peak_dps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_supporter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Gear fingerprint (fork export, local player only): exact weapon stats
    # snapshotted at quest start. NULL = pre-gear export ("Unknown").
    gear_raw: Mapped[float | None] = mapped_column(Float)
    gear_element: Mapped[float | None] = mapped_column(Float)
    gear_affinity: Mapped[float | None] = mapped_column(Float)


class WeaponIdentity(Base):
    """User-named weapon variant: one row per distinct gear fingerprint.

    The fork exports no weapon names, only (type, raw, element, affinity).
    The first sighting auto-creates an unlabeled row; the user names it
    once in the dashboard and every hunt with that fingerprint resolves.
    """
    __tablename__ = "weapon_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weapon_type: Mapped[str] = mapped_column(Text, nullable=False)
    gear_raw: Mapped[float] = mapped_column(Float, nullable=False)
    gear_element: Mapped[float] = mapped_column(Float, nullable=False)
    gear_affinity: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("weapon_type", "gear_raw", "gear_element",
                         "gear_affinity"),
    )


class DpsSnapshot(Base):
    __tablename__ = "dps_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    ts_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    cumulative_damage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    instant_dps: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    __table_args__ = (Index("idx_snapshots_hunt_ts", "hunt_id", "ts_offset_seconds"),)


class MonsterEvent(Base):
    __tablename__ = "monster_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False)
    monster_id: Mapped[int] = mapped_column(ForeignKey("monsters.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_offset_seconds: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("idx_events_hunt", "hunt_id", "monster_id"),
        UniqueConstraint("hunt_id", "monster_id", "event_type", "start_offset_seconds"),
    )


class MonsterHealthStep(Base):
    __tablename__ = "monster_health_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False)
    monster_id: Mapped[int] = mapped_column(ForeignKey("monsters.id"), nullable=False)
    ts_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    hp_fraction: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (Index("idx_hpsteps_hunt_ts", "hunt_id", "ts_offset_seconds"),)


class PlayerPin(Base):
    __tablename__ = "player_pins"

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"),
                                           primary_key=True)
    pinned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.utcnow)


class PlayerAbnormality(Base):
    __tablename__ = "player_abnormalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hunt_id: Mapped[int] = mapped_column(ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    abnormality_id: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    started_at_offset: Mapped[float] = mapped_column(Float, nullable=False)
    finished_at_offset: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("idx_abnormalities_hunt_player", "hunt_id", "player_id"),
    )
