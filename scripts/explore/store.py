import sqlite3
from selectolax.lexbor import LexborHTMLParser

DB = "internships.db"

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
    conn.commit()

def parse(html):
    tree = LexborHTMLParser(html)
    rows = []
    for card in tree.css("div.individual_internship"):
        h2 = card.css_first("h2.job-internship-name a")
        if h2 is None:
            continue

        def txt(sel):
            el = card.css_first(sel)
            return el.text(strip=True) if el else None

        rows.append({
            "url": "https://internshala.com" + h2.attributes.get("href", ""),
            "title": h2.text(strip=True),
            "company": txt(".company-name"),
            "location": txt(".location_link") or txt(".locations"),
            "stipend": txt(".stipend"),
            "duration": txt(".ic-16-calendar") and card.css_first(".ic-16-calendar").parent.text(strip=True),
            "posted": txt(".status-success") or txt(".status-inactive"),
        })
    return rows

def save(conn, rows):
    new = 0
    for r in rows:
        cur = conn.execute("""
            INSERT OR IGNORE INTO listings
            (url, title, company, location, stipend, duration, posted)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (r["url"], r["title"], r["company"], r["location"],
              r["stipend"], r["duration"], r["posted"]))
        new += cur.rowcount
    conn.commit()
    return new

if __name__ == "__main__":
    with open("step1_dump.html", encoding="utf-8") as f:
        html = f.read()

    rows = parse(html)
    print(f"parsed: {len(rows)}")

    conn = sqlite3.connect(DB)
    init_db(conn)
    added = save(conn, rows)
    print(f"new rows inserted: {added}")

    print("\n--- sample from DB ---")
    for row in conn.execute(
        "SELECT title, company, location, stipend FROM listings LIMIT 5"
    ):
        print(row)
    conn.close()
