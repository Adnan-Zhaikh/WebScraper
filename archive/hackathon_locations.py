# step10_hackathon_locations.py
import json
import sqlite3
import time
import httpx
from selectolax.lexbor import LexborHTMLParser

DB = "internships.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}

def add_columns(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(hackathons)")]
    for name in ("city", "venue", "location_raw"):
        if name not in cols:
            conn.execute(f"ALTER TABLE hackathons ADD COLUMN {name} TEXT")
    conn.commit()

def find_location(obj, depth=0):
    """Walk the JSON looking for location-ish keys."""
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
    resp = client.get(f"https://{slug}.devfolio.co")
    if resp.status_code != 200:
        return None
    tree = LexborHTMLParser(resp.text)
    script = tree.css_first("script#__NEXT_DATA__")
    if script is None:
        return None
    data = json.loads(script.text())
    return find_location(data.get("props", {}).get("pageProps", {}))

if __name__ == "__main__":
    conn = sqlite3.connect(DB)
    add_columns(conn)

    rows = conn.execute(
        "SELECT uuid, slug, name FROM hackathons WHERE is_online = 0 AND slug IS NOT NULL"
    ).fetchall()
    print(f"checking {len(rows)} in-person hackathons\n")

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        for uuid, slug, name in rows:
            try:
                loc = fetch_location(client, slug)
            except Exception as e:
                print(f"  {name}: failed ({type(e).__name__})")
                continue

            if not loc:
                print(f"  {name}: no location found")
                continue

            raw = ", ".join(dict.fromkeys(v for v in loc.values() if v))
            conn.execute(
                "UPDATE hackathons SET city = ?, venue = ?, location_raw = ? WHERE uuid = ?",
                (loc.get("city"), loc.get("name") or loc.get("venue_name"), raw, uuid),
            )
            print(f"  {name}: {raw}")
            time.sleep(1.5)

    conn.commit()

    print("\n--- results ---")
    for row in conn.execute("""
        SELECT name, city, location_raw FROM hackathons
        WHERE is_online = 0 ORDER BY starts_at
    """):
        print(row)
    conn.close()
