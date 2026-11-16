import json
import sqlite3
from selectolax.lexbor import LexborHTMLParser

DB = "internships.db"

def init_hackathon_table(conn):
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
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

def parse_hackathons(html):
    data = json.loads(LexborHTMLParser(html).css_first("script#__NEXT_DATA__").text())
    buckets = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]

    rows = []
    for status, items in buckets.items():
        for h in items:
            settings = h.get("settings") or {}
            themes = [t.get("theme", {}).get("name") for t in (h.get("themes") or [])]
            rows.append({
                "uuid": h["uuid"],
                "slug": h.get("slug"),
                "name": h.get("name"),
                "url": f"https://{h.get('slug')}.devfolio.co" if h.get("slug") else None,
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

if __name__ == "__main__":
    with open("devfolio_dump.html", encoding="utf-8") as f:
        html = f.read()

    rows = parse_hackathons(html)
    print(f"parsed {len(rows)} hackathons")

    conn = sqlite3.connect(DB)
    init_hackathon_table(conn)

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

    print(f"new rows: {new}")
    print("total hackathons:", conn.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0])

    print("\n--- open, online only ---")
    for row in conn.execute("""
        SELECT name, starts_at, participants_count, themes FROM hackathons
        WHERE status = 'open' AND is_online = 1
        ORDER BY starts_at LIMIT 5
    """):
        print(row)

    print("\n--- open, in-person ---")
    for row in conn.execute("""
        SELECT name, starts_at, participants_count FROM hackathons
        WHERE status = 'open' AND is_online = 0
        ORDER BY starts_at LIMIT 5
    """):
        print(row)

    conn.close()
