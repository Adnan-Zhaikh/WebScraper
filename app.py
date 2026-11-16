import sqlite3
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import subprocess
from fastapi import BackgroundTasks
from fastapi.staticfiles import StaticFiles




DB = "internships.db"
app = FastAPI(title="Mumbai Internships & Hackathons")


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/hackathons", response_class=HTMLResponse)
def hackathons_page():
    return open("index.html", encoding="utf-8").read()

def query(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

_refreshing = {"running": False, "last": None, "result": None}

def run_refresh():
    _refreshing["running"] = True
    try:
        proc = subprocess.run(
            ["python", "refresh.py"],
            capture_output=True, text=True, timeout=600,
        )
        _refreshing["result"] = {
            "ok": proc.returncode == 0,
            "out": proc.stdout[-2000:],
            "err": proc.stderr[-1000:],
        }
    except Exception as e:
        _refreshing["result"] = {"ok": False, "out": "", "err": str(e)}
    finally:
        _refreshing["running"] = False
        _refreshing["last"] = __import__("datetime").datetime.utcnow().isoformat()

@app.post("/refresh")
def refresh(background: BackgroundTasks):
    if _refreshing["running"]:
        return {"status": "already running"}
    background.add_task(run_refresh)
    return {"status": "started"}

@app.get("/refresh/status")
def refresh_status():
    return _refreshing


@app.get("/api/internships")
def internships(limit: int = Query(50, le=200)):
    return query("""
        SELECT title, company, location, stipend, duration, posted, url, source
        FROM listings
        ORDER BY first_seen DESC, id DESC
        LIMIT ?
    """, (limit,))

@app.get("/api/hackathons")
def hackathons(status: str | None = None, online: bool | None = None):
    sql = "SELECT name, url, starts_at, ends_at, is_online, participants_count, themes, status FROM hackathons WHERE 1=1"
    sql = "SELECT name, url, starts_at, ends_at, is_online, city, location_raw, in_india, participants_count, themes, status FROM hackathons WHERE 1=1"
    sql = """SELECT name, url, starts_at, ends_at, is_online, city, location_raw,
                participants_count, themes, status
         FROM hackathons WHERE 1=1"""
    sql = """SELECT name, url, starts_at, ends_at, is_online, city, location_raw,
                in_india, participants_count, themes, status
         FROM hackathons WHERE 1=1"""
    sql = """SELECT name, url, starts_at, ends_at, is_online, city, location_raw,
                in_india, participants_count, themes, status, source
         FROM hackathons
         WHERE (ends_at IS NULL OR ends_at >= date('now'))
           AND (:source = '' OR source = :source)"""
    


    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if online is not None:
        sql += " AND is_online = ?"
        params.append(1 if online else 0)
    sql += " ORDER BY starts_at"

    return query(sql, params)


@app.get("/api/stats")
def stats():
    return {
        "internships": query("SELECT COUNT(*) c FROM listings")[0]["c"],
        "hackathons": query("SELECT COUNT(*) c FROM hackathons")[0]["c"],
        "open_hackathons": query("SELECT COUNT(*) c FROM hackathons WHERE status='open'")[0]["c"],
        "mumbai": query("SELECT COUNT(*) c FROM listings WHERE location LIKE '%Mumbai%'")[0]["c"],
        "remote": query("SELECT COUNT(*) c FROM listings WHERE location LIKE '%home%'")[0]["c"],
    }

@app.get("/", response_class=HTMLResponse)
def index():
    return open("index.html", encoding="utf-8").read()
