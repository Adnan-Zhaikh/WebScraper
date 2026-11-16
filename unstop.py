"""Scrape Unstop hackathons into the shared hackathons table."""
import json
import re
import sqlite3
import time

import httpx

DB = "internships.db"
BASE = "https://unstop.com"
API = "https://unstop.com/api/public/opportunity/search-result"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://unstop.com/hackathons",
}

def name_key(name, starts_at):
    n = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return f"{n}|{(starts_at or '')[:10]}"

def fetch_page(client, page):
    params = {
        "opportunity": "hackathons",
        "page": page,
        "per_page": 30,
        "sortBy": "recent",
    }
    resp = client.get(API, params=params)
    if resp.status_code != 200:
        print(f"  page {page}: HTTP {resp.status_code}")
        return None
    return resp.json()

def parse_items(payload):
    data = payload.get("data") or {}
    items = data.get("data") or []
    rows = []
    for it in items:
        oid = it.get("id")
        if oid is None:
            continue
        public = it.get("public_url") or it.get("seo_url") or ""
        rows.append({
            "uuid": f"unstop-{oid}",
            "slug": None,
            "name": (it.get("title") or "").strip(),
            "url": f"{BASE}/{public}" if public else None,
            "type": it.get("type"),
            "starts_at": it.get("start_date"),
            "ends_at": it.get("end_date"),
            "is_online": 1 if (it.get("region") == "online" or it.get("is_online")) else 0,
            "participants_count": it.get("registerCount") or 0,
            "themes": ", ".join(
                t.get("name") for t in (it.get("filters") or [])
                if isinstance(t, dict) and t.get("name")
            ),
            "reg_ends_at": it.get("end_date"),
            "status": "open" if (it.get("status") or "").lower() in ("open", "live") else "upcoming",
            "city": (it.get("address_with_country_logo") or {}).get("city") if isinstance(it.get("address_with_country_logo"), dict) else None,
            "location_raw": it.get("region") or None,
            "in_india": 0 if (it.get("region") or "").lower() in ("online",) and False else 1,
            "source": "unstop",
        })
    return rows, data.get("total"), data.get("last_page")

def main():
    conn = sqlite3.connect(DB)
    total_new = 0

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        page = 1
        while True:
            payload = fetch_page(client, page)
            if not payload:
                break

            rows, total, last_page = parse_items(payload)
            new = 0
            for r in rows:
                r["name_key"] = name_key(r["name"], r["starts_at"])

                # skip if the same event already exists from another source
                dupe = conn.execute(
                    "SELECT 1 FROM hackathons WHERE name_key = ?", (r["name_key"],)
                ).fetchone()
                if dupe:
                    continue

                cur = conn.execute("""
                    INSERT OR IGNORE INTO hackathons
                    (uuid, slug, name, url, type, starts_at, ends_at, is_online,
                     participants_count, themes, reg_ends_at, status, city,
                     location_raw, in_india, source, name_key)
                    VALUES (:uuid, :slug, :name, :url, :type, :starts_at, :ends_at, :is_online,
                            :participants_count, :themes, :reg_ends_at, :status, :city,
                            :location_raw, :in_india, :source, :name_key)
                """, r)
                new += cur.rowcount

            conn.commit()
            total_new += new
            print(f"  page {page}: {len(rows)} items, {new} new  (total {total}, last page {last_page})")

            if not last_page or page >= last_page:
                break
            page += 1
            time.sleep(2.5)

    print(f"\nnew unstop hackathons: {total_new}")
    print("hackathons in db:", conn.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0])
    conn.close()

if __name__ == "__main__":
    main()
