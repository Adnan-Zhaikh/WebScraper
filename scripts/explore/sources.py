import sqlite3
import time
import httpx
from selectolax.lexbor import LexborHTMLParser
import re

DB = "internships.db"

SOURCES = {
    "internshala-mumbai": "https://internshala.com/internships/internship-in-mumbai/",
    "internshala-remote": "https://internshala.com/internships/work-from-home-internships/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

def parse(html, source):
    tree = LexborHTMLParser(html)
    rows = []
    for card in tree.css("div.individual_internship"):
        a = card.css_first("h2.job-internship-name a")
        if a is None:
            continue

        def txt(sel):
            el = card.css_first(sel)
            return el.text(strip=True) if el else None

        rows.append({
            "url": "https://internshala.com" + a.attributes.get("href", ""),
            "title": a.text(strip=True),
            "company": txt(".company-name"),
            "location": txt(".location_link") or txt(".locations"),
            "stipend": txt(".stipend"),
            "duration": txt(".ic-16-calendar") and card.css_first(".ic-16-calendar").parent.text(strip=True),
            "posted": txt(".status-success") or txt(".status-inactive"),
            "source": source,
        })
    return rows

import re

def clean(s):
    if not s:
        return None
    return re.sub(r"\s+", " ", s.replace("fromhome", "from home")).strip()

def main():
    conn = sqlite3.connect(DB)
    total_new = 0

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        for source, url in SOURCES.items():
            resp = client.get(url)
            print(f"{source}: status={resp.status_code} bytes={len(resp.text)}")

            if resp.status_code != 200:
                print(f"  skipped {source}")
                continue

            rows = parse(resp.text, source)
            print(f"  parsed {len(rows)} listings")

            for r in rows:
                cur = conn.execute("""
                    INSERT OR IGNORE INTO listings
                    (url, title, company, location, stipend, duration, posted, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (r["url"], r["title"], r["company"], r["location"],
                      r["stipend"], r["duration"], r["posted"], r["source"]))
                total_new += cur.rowcount

            conn.commit()
            time.sleep(2)  # be polite between requests

    print(f"\nnew rows this run: {total_new}")
    print("total in DB:", conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0])

    print("\n--- Mumbai sample ---")
    for row in conn.execute("""
        SELECT title, company, location, stipend FROM listings
        WHERE source = 'internshala-mumbai' LIMIT 5
    """):
        print(row)

    print("\n--- Remote sample ---")
    for row in conn.execute("""
        SELECT title, company, location, stipend FROM listings
        WHERE source = 'internshala-remote' LIMIT 5
    """):
        print(row)

    conn.close()

if __name__ == "__main__":
    main()
