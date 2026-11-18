import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

import refresh
from db import database_url, init_db

BASE_DIR = Path(__file__).resolve().parent
REFRESH_COOLDOWN_MIN = int(os.environ.get("REFRESH_COOLDOWN_MINUTES", "10"))

# Dates are compared in IST so "ends today" still counts as open for Indian users.
NOT_ENDED = """(ends_at IS NULL OR
    (ends_at AT TIME ZONE 'Asia/Kolkata')::date >= (now() AT TIME ZONE 'Asia/Kolkata')::date)"""

pool = ConnectionPool(
    database_url(),
    min_size=1,
    max_size=5,
    open=False,
    kwargs={
        "row_factory": dict_row,
        "autocommit": True,
        "prepare_threshold": None,  # keeps things working behind pgbouncer-style poolers
    },
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    pool.wait()
    with pool.connection() as conn:
        init_db(conn)  # creates tables on first run
    yield
    pool.close()


app = FastAPI(title="Mumbai Internships & Hackathons", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def query(sql, params=()):
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


# ---------- pages ----------

@app.get("/")
@app.get("/hackathons")
def page():
    return FileResponse(BASE_DIR / "index.html", media_type="text/html")


@app.get("/healthz")
def healthz():
    query("SELECT 1")
    return {"ok": True}


# ---------- refresh ----------

def refresh_state():
    latest = query("""
        SELECT started_at,
               (finished_at IS NULL AND started_at > now() - interval '15 minutes') AS running,
               EXTRACT(EPOCH FROM (now() - started_at))::int AS age_seconds
        FROM refresh_runs ORDER BY id DESC LIMIT 1
    """)
    done = query("""
        SELECT finished_at, ok, new_internships, new_hackathons, error
        FROM refresh_runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1
    """)
    latest, done = (latest[0] if latest else None), (done[0] if done else None)
    return {
        "running": bool(latest and latest["running"]),
        "last_started": latest["started_at"].isoformat() if latest else None,
        "age_seconds": latest["age_seconds"] if latest else None,
        "last_finished": done["finished_at"].isoformat() if done else None,
        "last_ok": done["ok"] if done else None,
        "new_internships": done["new_internships"] if done else None,
        "new_hackathons": done["new_hackathons"] if done else None,
        "error": done["error"] if done else None,
    }


def run_refresh():
    try:
        refresh.run()
    except Exception as e:  # already recorded in refresh_runs by refresh.run()
        print(f"refresh failed: {type(e).__name__}: {e}")


@app.post("/refresh")
def start_refresh(background: BackgroundTasks):
    state = refresh_state()
    if state["running"]:
        return {"status": "already_running"}
    if state["age_seconds"] is not None and state["age_seconds"] < REFRESH_COOLDOWN_MIN * 60:
        return JSONResponse(
            {"status": "cooldown", "retry_in": REFRESH_COOLDOWN_MIN * 60 - state["age_seconds"]},
            status_code=429,
        )
    background.add_task(run_refresh)
    return {"status": "started"}


@app.get("/refresh/status")
def refresh_status():
    return refresh_state()


# ---------- data ----------

@app.get("/api/internships")
def internships(limit: int = Query(50, ge=1, le=500)):
    return query("""
        SELECT title, company, location, stipend, duration, posted, url, source
        FROM listings
        ORDER BY first_seen DESC, id DESC
        LIMIT %s
    """, (limit,))


@app.get("/api/hackathons")
def hackathons(status: str | None = None, online: bool | None = None, source: str | None = None):
    sql = f"""SELECT name, url, starts_at, ends_at, reg_ends_at, is_online, city, location_raw,
                     in_india, participants_count, themes, status, source
              FROM hackathons
              WHERE {NOT_ENDED}"""
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if online is not None:
        sql += " AND is_online = %s"
        params.append(online)
    if source:
        sql += " AND source = %s"
        params.append(source)
    sql += " ORDER BY ends_at ASC NULLS LAST, id"
    return query(sql, params)


@app.get("/api/stats")
def stats():
    return query(f"""
        SELECT
          (SELECT count(*) FROM listings)                                        AS internships,
          (SELECT count(*) FROM listings WHERE location ILIKE '%%mumbai%%')      AS mumbai,
          (SELECT count(*) FROM listings
             WHERE location ILIKE '%%home%%' OR location ILIKE '%%remote%%')     AS remote,
          (SELECT count(*) FROM hackathons)                                      AS hackathons,
          (SELECT count(*) FROM hackathons WHERE status = 'open')                AS open_hackathons,
          (SELECT count(*) FROM hackathons WHERE {NOT_ENDED})                    AS upcoming_hackathons
    """)[0]
