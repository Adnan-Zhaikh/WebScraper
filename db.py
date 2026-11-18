"""Postgres connection settings + schema. Shared by app.py and refresh.py."""
import os

try:  # optional: lets you keep DATABASE_URL in a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: "
            "postgresql://user:password@localhost:5432/internships"
        )
    return url


SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url         TEXT UNIQUE NOT NULL,
    title       TEXT,
    company     TEXT,
    location    TEXT,
    stipend     TEXT,
    duration    TEXT,
    posted      TEXT,
    source      TEXT NOT NULL DEFAULT 'internshala',
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS listings_first_seen_idx ON listings (first_seen DESC, id DESC);

CREATE TABLE IF NOT EXISTS hackathons (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uuid                TEXT UNIQUE NOT NULL,
    slug                TEXT,
    name                TEXT NOT NULL,
    url                 TEXT,
    type                TEXT,
    starts_at           TIMESTAMPTZ,
    ends_at             TIMESTAMPTZ,
    is_online           BOOLEAN NOT NULL DEFAULT FALSE,
    participants_count  INTEGER NOT NULL DEFAULT 0,
    themes              TEXT,
    reg_ends_at         TIMESTAMPTZ,
    status              TEXT,
    city                TEXT,
    venue               TEXT,
    location_raw        TEXT,
    in_india            BOOLEAN,
    location_checked    BOOLEAN NOT NULL DEFAULT FALSE,
    source              TEXT NOT NULL DEFAULT 'devfolio',
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS hackathons_ends_at_idx ON hackathons (ends_at);

CREATE TABLE IF NOT EXISTS refresh_runs (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    ok               BOOLEAN,
    new_internships  INTEGER,
    new_hackathons   INTEGER,
    error            TEXT
);
"""


def init_db(conn):
    """Create tables if missing. Safe to call on every startup."""
    conn.execute(SCHEMA)
