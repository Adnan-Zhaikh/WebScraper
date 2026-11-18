"""Scrape Internshala + Devfolio into Postgres.

Safe to re-run: internships dedup on url, hackathons upsert on uuid (so status,
dates and participant counts stay fresh). Run directly (`python refresh.py`,
e.g. from a cron job) or via the /refresh endpoint.
"""
import json
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin

import httpx
import psycopg
from selectolax.lexbor import LexborHTMLParser

from db import database_url, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

INTERNSHALA_SOURCES = {
    "internshala-mumbai": "https://internshala.com/internships/internship-in-mumbai/",
    "internshala-remote": "https://internshala.com/internships/work-from-home-internships/",
}
DEVFOLIO_URL = "https://devfolio.co/hackathons"

# word-boundary match so e.g. "uk" doesn't match inside another place name
FOREIGN_RE = re.compile(
    r"\b(thailand|london|uk|usa|united states|singapore|dubai|uae)\b", re.I
)

LOCK_ID = 727001  # Postgres advisory lock: only one refresh at a time, across all processes


# ---------- helpers ----------

def clean(s):
    if not s:
        return None
    return re.sub(r"\s+", " ", s.replace("fromhome", "from home")).strip()


def parse_ts(value):
    """ISO string -> aware datetime, or None if missing/unparseable."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------- internshala ----------

def parse_internships(html, source):
    tree = LexborHTMLParser(html)
    rows = []
    for card in tree.css("div.individual_internship"):
        a = card.css_first("h2.job-internship-name a")
        href = a.attributes.get("href") if a is not None else None
        if not href:
            continue

        def txt(sel):
            el = card.css_first(sel)
            return el.text(strip=True) if el else None

        cal = card.css_first(".ic-16-calendar")
        rows.append({
            "url": urljoin("https://internshala.com", href),
            "title": a.text(strip=True),
            "company": clean(txt(".company-name")),
            "location": clean(txt(".location_link") or txt(".locations")),
            "stipend": clean(txt(".stipend")),
            "duration": clean(cal.parent.text(strip=True)) if cal and cal.parent else None,
            "posted": clean(txt(".status-success") or txt(".status-inactive")),
            "source": source,
        })
    return rows


def scrape_internships(conn, client):
    """Returns (new_rows, errors)."""
    total_new, errors = 0, []
    for source, url in INTERNSHALA_SOURCES.items():
        try:
            resp = client.get(url)
        except Exception as e:
            errors.append(f"{source}: request failed ({type(e).__name__})")
            print(f"  {errors[-1]}")
            continue

        if resp.status_code != 200:
            errors.append(f"{source}: HTTP {resp.status_code}")
            print(f"  {errors[-1]}, skipped")
            continue

        rows = parse_internships(resp.text, source)
        if not rows:
            # 200 but nothing parsed = site layout changed or we were served a block page
            errors.append(f"{source}: 0 listings parsed (layout change or blocked?)")
            print(f"  {errors[-1]}")
            continue

        new = 0
        for r in rows:
            cur = conn.execute("""
                INSERT INTO listings (url, title, company, location, stipend, duration, posted, source)
                VALUES (%(url)s, %(title)s, %(company)s, %(location)s, %(stipend)s,
                        %(duration)s, %(posted)s, %(source)s)
                ON CONFLICT (url) DO NOTHING
            """, r)
            new += cur.rowcount
        total_new += new
        print(f"  {source}: {len(rows)} parsed, {new} new")
        time.sleep(2)
    return total_new, errors


# ---------- devfolio ----------

def parse_hackathons(html):
    script = LexborHTMLParser(html).css_first("script#__NEXT_DATA__")
    if script is None:
        raise ValueError("devfolio: __NEXT_DATA__ not found (layout change or blocked?)")
    try:
        data = json.loads(script.text())
        buckets = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"devfolio: unexpected data shape ({type(e).__name__}: {e})")

    rows = []
    for status, items in buckets.items():
        if not isinstance(items, list):
            continue
        for h in items:
            if not h.get("uuid") or not h.get("name"):
                continue
            settings = h.get("settings") or {}
            themes = [(t.get("theme") or {}).get("name") for t in (h.get("themes") or [])]
            slug = h.get("slug")
            rows.append({
                "uuid": h["uuid"],
                "slug": slug,
                "name": h["name"],
                "url": f"https://{slug}.devfolio.co" if slug else None,
                "type": h.get("type"),
                "starts_at": parse_ts(h.get("starts_at")),
                "ends_at": parse_ts(h.get("ends_at")),
                "is_online": bool(h.get("is_online")),
                "participants_count": h.get("participants_count") or 0,
                "themes": ", ".join(t for t in themes if t),
                "reg_ends_at": parse_ts(settings.get("reg_ends_at")),
                "status": status.replace("_hackathons", ""),
            })
    return rows


def find_location(obj, depth=0):
    if depth > 8:
        return None
    if isinstance(obj, dict):
        for key in ("city", "venue_name", "venue", "address", "location"):
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return {key: v.strip()}
            if isinstance(v, dict):
                inner = {k: v[k] for k in ("city", "name", "address", "state", "country")
                         if isinstance(v.get(k), str) and v[k].strip()}
                if inner:
                    return inner
        for v in obj.values():
            hit = find_location(v, depth + 1)
            if hit:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find_location(v, depth + 1)
            if hit:
                return hit
    return None


def fetch_location(client, slug):
    """Returns (page_loaded, location_dict_or_None). page_loaded=False means
    'try again next time' (network error / non-200); True means we looked."""
    try:
        resp = client.get(f"https://{slug}.devfolio.co")
    except Exception:
        return False, None
    if resp.status_code != 200:
        return False, None
    script = LexborHTMLParser(resp.text).css_first("script#__NEXT_DATA__")
    if script is None:
        return True, None
    try:
        data = json.loads(script.text())
    except json.JSONDecodeError:
        return True, None
    return True, find_location(data.get("props", {}).get("pageProps", {}))


def scrape_hackathons(conn, client):
    """Returns (new_rows, errors)."""
    try:
        resp = client.get(DEVFOLIO_URL)
    except Exception as e:
        msg = f"devfolio: request failed ({type(e).__name__})"
        print(f"  {msg}")
        return 0, [msg]

    if resp.status_code != 200:
        msg = f"devfolio: HTTP {resp.status_code}"
        print(f"  {msg}, skipped")
        return 0, [msg]

    try:
        rows = parse_hackathons(resp.text)
    except ValueError as e:
        print(f"  {e}")
        return 0, [str(e)]

    new = 0
    for r in rows:
        # Upsert: status / dates / participant counts change over time, so refresh them.
        cur = conn.execute("""
            INSERT INTO hackathons
                (uuid, slug, name, url, type, starts_at, ends_at, is_online,
                 participants_count, themes, reg_ends_at, status)
            VALUES (%(uuid)s, %(slug)s, %(name)s, %(url)s, %(type)s, %(starts_at)s, %(ends_at)s,
                    %(is_online)s, %(participants_count)s, %(themes)s, %(reg_ends_at)s, %(status)s)
            ON CONFLICT (uuid) DO UPDATE SET
                name = EXCLUDED.name, url = EXCLUDED.url, type = EXCLUDED.type,
                starts_at = EXCLUDED.starts_at, ends_at = EXCLUDED.ends_at,
                is_online = EXCLUDED.is_online,
                participants_count = EXCLUDED.participants_count,
                themes = EXCLUDED.themes, reg_ends_at = EXCLUDED.reg_ends_at,
                status = EXCLUDED.status
            RETURNING (xmax = 0) AS inserted
        """, r)
        if cur.fetchone()[0]:
            new += 1
    print(f"  devfolio: {len(rows)} parsed, {new} new")

    # location pass: only in-person, not-yet-ended events we haven't looked up yet
    pending = conn.execute("""
        SELECT uuid, slug, name FROM hackathons
        WHERE NOT is_online AND slug IS NOT NULL AND NOT location_checked
          AND (ends_at IS NULL OR ends_at >= now())
    """).fetchall()
    print(f"  locations: {len(pending)} to resolve")

    for uuid, slug, name in pending:
        loaded, loc = fetch_location(client, slug)
        if not loaded:
            print(f"    {name}: page failed to load, will retry next refresh")
            time.sleep(1.5)
            continue
        if not loc:
            conn.execute("UPDATE hackathons SET location_checked = TRUE WHERE uuid = %s", (uuid,))
            print(f"    {name}: none found")
            time.sleep(1.5)
            continue
        raw = ", ".join(dict.fromkeys(v for v in loc.values() if v))
        conn.execute("""
            UPDATE hackathons
            SET city = %s, venue = %s, location_raw = %s, in_india = %s, location_checked = TRUE
            WHERE uuid = %s
        """, (loc.get("city"), loc.get("name") or loc.get("venue_name"),
              raw, not FOREIGN_RE.search(raw), uuid))
        print(f"    {name}: {raw}")
        time.sleep(1.5)

    return new, []


# ---------- main ----------

def run():
    """Run one full refresh. Returns a dict; never runs twice at once."""
    started = time.time()
    print("refresh started")
    # autocommit: each statement is saved immediately, so a crash/timeout
    # halfway through doesn't throw away everything already scraped.
    with psycopg.connect(database_url(), autocommit=True) as conn:
        init_db(conn)
        if not conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
            print("another refresh is already running, exiting")
            return {"status": "already_running"}

        run_id = conn.execute("INSERT INTO refresh_runs DEFAULT VALUES RETURNING id").fetchone()[0]
        try:
            with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
                print("internshala:")
                new_ints, err1 = scrape_internships(conn, client)
                print("devfolio:")
                new_hacks, err2 = scrape_hackathons(conn, client)

            errors = err1 + err2
            total_sources = len(INTERNSHALA_SOURCES) + 1
            ok = len(errors) < total_sources  # ok if at least one source worked
            conn.execute("""
                UPDATE refresh_runs SET finished_at = now(), ok = %s,
                    new_internships = %s, new_hackathons = %s, error = %s
                WHERE id = %s
            """, (ok, new_ints, new_hacks, "; ".join(errors)[:500] or None, run_id))
        except Exception as e:
            conn.execute(
                "UPDATE refresh_runs SET finished_at = now(), ok = FALSE, error = %s WHERE id = %s",
                (f"{type(e).__name__}: {e}"[:500], run_id),
            )
            raise
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))

    print(f"\nnew internships: {new_ints}  |  new hackathons: {new_hacks}")
    print(f"done in {time.time() - started:.1f}s")
    return {"status": "done", "ok": ok, "errors": errors}


def main():
    result = run()
    return 0 if result.get("status") == "already_running" or result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
