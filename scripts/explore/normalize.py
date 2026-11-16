# step11_normalize.py
import sqlite3, re

DB = "internships.db"
conn = sqlite3.connect(DB)

cols = [r[1] for r in conn.execute("PRAGMA table_info(hackathons)")]
if "in_india" not in cols:
    conn.execute("ALTER TABLE hackathons ADD COLUMN in_india INTEGER")

FOREIGN = ("thailand", "london", "uk", "usa", "united states", "singapore", "dubai", "uae")

for uuid, raw in conn.execute(
    "SELECT uuid, location_raw FROM hackathons WHERE is_online = 0"
).fetchall():
    text = (raw or "").lower()
    foreign = any(w in text for w in FOREIGN)
    conn.execute(
        "UPDATE hackathons SET in_india = ? WHERE uuid = ?",
        (0 if foreign else 1, uuid),
    )

conn.commit()
for row in conn.execute("""
    SELECT name, city, in_india FROM hackathons
    WHERE is_online = 0 ORDER BY in_india DESC, city
"""):
    print(row)
conn.close()
