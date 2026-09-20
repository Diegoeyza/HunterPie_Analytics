"""models <-> schema.sql <-> migrated-DB consistency (drift guard)."""
import re
import tempfile
from pathlib import Path

from sqlalchemy import MetaData, create_engine

from app import db as dbmod
from app.models import Base


def _schema_tables() -> dict[str, set[str]]:
    """Parse db/schema.sql into {table: {columns}} (CREATE TABLE only)."""
    sql = (Path(__file__).resolve().parent.parent.parent
           / "db" / "schema.sql").read_text()
    # Strip -- comments first (they may contain ");" which would truncate
    # the CREATE TABLE body match below).
    sql = re.sub(r"--[^\n]*", "", sql)
    tables: dict[str, set[str]] = {}
    for m in re.finditer(
            r"CREATE TABLE (\w+)\s*\((.*?)\);", sql, re.S):
        name, body = m.group(1), m.group(2)
        cols = set()
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith(("CHECK", "PRIMARY", "FOREIGN",
                                            "UNIQUE", "CONSTRAINT")):
                continue
            cols.add(line.split()[0])
        tables[name] = cols
    return tables


def test_models_match_schema_sql():
    """Every model table/column exists in schema.sql and vice versa."""
    schema = _schema_tables()
    model_tables = {t.name: {c.name for c in t.columns}
                    for t in Base.metadata.tables.values()}
    assert set(model_tables) == set(schema), (
        set(model_tables) ^ set(schema))
    for table, cols in model_tables.items():
        missing = set(cols) - schema[table]
        # created_at/imported_at defaults vary textually; columns must exist
        assert not missing, f"{table} missing from schema.sql: {missing}"
        extra = schema[table] - set(cols)
        assert not extra, f"{table} has schema.sql-only columns: {extra}"


def test_fresh_db_has_all_tables_and_version():
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    try:
        dbmod.init_db(path)
        eng = create_engine(f"sqlite:///{path}")
        with eng.connect() as conn:
            from sqlalchemy import text
            version = conn.execute(
                text("PRAGMA user_version")).scalar_one()
            assert version == dbmod.LATEST_VERSION
            tables = {r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"))}
        reflected = MetaData()
        reflected.reflect(bind=create_engine(f"sqlite:///{path}"))
        assert {t for t in reflected.tables} >= set(Base.metadata.tables)
        assert tables >= set(Base.metadata.tables)
    finally:
        Path(path).unlink(missing_ok=True)


def test_migrate_is_idempotent():
    import os
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        dbmod.init_db(path)
        assert dbmod.migrate(db_path=path) == dbmod.LATEST_VERSION
        assert dbmod.migrate(db_path=path) == dbmod.LATEST_VERSION
    finally:
        Path(path).unlink(missing_ok=True)
