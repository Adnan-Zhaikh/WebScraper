"""Scrape Internshala + Devfolio into SQLite. Safe to re-run: dedups on url/uuid."""
import json
import re
import sqlite3
import sys
import time

import httpx
from selectolax.lexbor import LexborHTMLParser

DB = "internships.db"

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

FOREIGN = ("thailand", "london", "uk", "usa", "united states", "singapore", "dubai", "uae")


# ---------- helpers ----------

def clean(s):
    if not s:
        return None
    return re.sub(r"\s+", " ", s.replace("fromhome", "from home")).strip()


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            company TEXT,
            location TEXT,
            stipend TEXT,
            duration TEXT,
            posted TEXT,
            source TEXT DEFAULT 'internshala',
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hackathons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            slug TEXT,
            name TEXT NOT NULL,
            url TEXT,
            type TEXT,
            starts_at TEXT,
            ends_at TEXT,
            is_online INTEGER,
            participants_count INTEGER,
            themes TEXT,
            reg_ends_at TEXT,
            status TEXT,
            city TEXT,
            venue TEXT,
            location_raw TEXT,
            in_india INTEGER,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


# ---------- internshala ----------

def parse_internships(html, source):
    tree = LexborHTMLParser(html)
    rows = []
    for card in tree.css("div.individual_internship"):
        a = card.css_first("h2.job-internship-name a")
        if a is None:
            continue

        def txt(sel):
            el = card.css_first(sel)
            return el.text(strip=True) if el else None

        cal = card.css_first(".ic-16-calendar")
        rows.append({
            "url": "https://internshala.com" + a.attributes.get("href", ""),
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
    total_new = 0
    for source, url in INTERNSHALA_SOURCES.items():
        try:
            resp = client.get(url)
        except Exception as e:
            print(f"  {source}: request failed ({type(e).__name__})")
            continue

        if resp.status_code != 200:
            print(f"  {source}: HTTP {resp.status_code}, skipped")
            continue

        rows = parse_internships(resp.text, source)
        new = 0
        for r in rows:
            cur = conn.execute("""
                INSERT OR IGNORE INTO listings
                (url, title, company, location, stipend, duration, posted, source)
                VALUES (:url, :title, :company, :location, :stipend, :duration, :posted, :source)
            """, r)
            new += cur.rowcount
        conn.commit()
        total_new += new
        print(f"  {source}: {len(rows)} parsed, {new} new")
        time.sleep(2)
    return total_new


# ---------- devfolio ----------

def parse_hackathons(html):
    script = LexborHTMLParser(html).css_first("script#__NEXT_DATA__")
    if script is None:
        return []
    data = json.loads(script.text())
    buckets = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]

    rows = []
    for status, items in buckets.items():
        for h in items:
            settings = h.get("settings") or {}
            themes = [t.get("theme", {}).get("name") for t in (h.get("themes") or [])]
            slug = h.get("slug")
            rows.append({
                "uuid": h["uuid"],
                "slug": slug,
                "name": h.get("name"),
                "url": f"https://{slug}.devfolio.co" if slug else None,
                "type": h.get("type"),
                "starts_at": h.get("starts_at"),
                "ends_at": h.get("ends_at"),
                "is_online": 1 if h.get("is_online") else 0,
                "participants_count": h.get("participants_count") or 0,
                "themes": ", ".join(t for t in themes if t),
                "reg_ends_at": settings.get("reg_ends_at"),
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
    try:
        resp = client.get(f"https://{slug}.devfolio.co")
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    script = LexborHTMLParser(resp.text).css_first("script#__NEXT_DATA__")
    if script is None:
        return None
    data = json.loads(script.text())
    return find_location(data.get("props", {}).get("pageProps", {}))


def scrape_hackathons(conn, client):
    try:
        resp = client.get(DEVFOLIO_URL)
    except Exception as e:
        print(f"  devfolio: request failed ({type(e).__name__})")
        return 0

    if resp.status_code != 200:
        print(f"  devfolio: HTTP {resp.status_code}, skipped")
        return 0

    rows = parse_hackathons(resp.text)
    new = 0
    for r in rows:
        cur = conn.execute("""
            INSERT OR IGNORE INTO hackathons
            (uuid, slug, name, url, type, starts_at, ends_at, is_online,
             participants_count, themes, reg_ends_at, status)
            VALUES (:uuid, :slug, :name, :url, :type, :starts_at, :ends_at, :is_online,
                    :participants_count, :themes, :reg_ends_at, :status)
        """, r)
        new += cur.rowcount
    conn.commit()
    print(f"  devfolio: {len(rows)} parsed, {new} new")

    # location pass: only in-person ones still missing a city
    pending = conn.execute("""
        SELECT uuid, slug, name FROM hackathons
        WHERE is_online = 0 AND slug IS NOT NULL AND city IS NULL
    """).fetchall()
    print(f"  locations: {len(pending)} to resolve")

    for uuid, slug, name in pending:
        loc = fetch_location(client, slug)
        if not loc:
            print(f"    {name}: none found")
            time.sleep(1.5)
            continue
        raw = ", ".join(dict.fromkeys(v for v in loc.values() if v))
        foreign = any(w in raw.lower() for w in FOREIGN)
        conn.execute("""
            UPDATE hackathons
            SET city = ?, venue = ?, location_raw = ?, in_india = ?
            WHERE uuid = ?
        """, (loc.get("city"), loc.get("name") or loc.get("venue_name"),
              raw, 0 if foreign else 1, uuid))
        print(f"    {name}: {raw}")
        time.sleep(1.5)

    conn.commit()
    return new


# ---------- main ----------

def main():
    started = time.time()
    print("refresh started")
    conn = sqlite3.connect(DB)
    init_db(conn)

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        print("internshala:")
        new_ints = scrape_internships(conn, client)
        print("devfolio:")
        new_hacks = scrape_hackathons(conn, client)

    ints_total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    hacks_total = conn.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0]
    conn.close()

    print(f"\nnew internships: {new_ints}  |  new hackathons: {new_hacks}")
    print(f"totals: {ints_total} internships, {hacks_total} hackathons")
    print(f"done in {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
