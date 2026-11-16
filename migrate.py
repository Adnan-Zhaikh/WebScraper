# step12_migrate.py
import sqlite3

conn = sqlite3.connect("internships.db")

cols = [r[1] for r in conn.execute("PRAGMA table_info(hackathons)")]
if "source" not in cols:
    conn.execute("ALTER TABLE hackathons ADD COLUMN source TEXT DEFAULT 'devfolio'")
    print("added source")
if "name_key" not in cols:
    conn.execute("ALTER TABLE hackathons ADD COLUMN name_key TEXT")
    print("added name_key")

# backfill name_key so cross-source dedup has something to compare
import re
def key(name, starts_at):
    n = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    d = (starts_at or "")[:10]
    return f"{n}|{d}"

for uuid, name, starts_at in conn.execute(
    "SELECT uuid, name, starts_at FROM hackathons WHERE name_key IS NULL"
).fetchall():
    conn.execute("UPDATE hackathons SET name_key = ? WHERE uuid = ?", (key(name, starts_at), uuid))

conn.execute("CREATE INDEX IF NOT EXISTS idx_hack_name_key ON hackathons(name_key)")
conn.commit()
print("done")
conn.close()
