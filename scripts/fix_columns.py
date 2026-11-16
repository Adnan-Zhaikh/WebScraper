# fix_columns.py
import sqlite3

conn = sqlite3.connect("internships.db")
cols = [r[1] for r in conn.execute("PRAGMA table_info(hackathons)")]

for name, kind in (("city", "TEXT"), ("venue", "TEXT"),
                   ("location_raw", "TEXT"), ("in_india", "INTEGER")):
    if name not in cols:
        conn.execute(f"ALTER TABLE hackathons ADD COLUMN {name} {kind}")
        print(f"added {name}")

conn.commit()
print("columns now:", [r[1] for r in conn.execute("PRAGMA table_info(hackathons)")])
conn.close()
