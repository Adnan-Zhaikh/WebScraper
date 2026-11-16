# step15_fix_status.py
import sqlite3

conn = sqlite3.connect("internships.db")

cur = conn.execute("""
    UPDATE hackathons
    SET status = CASE
        WHEN ends_at IS NULL THEN 'upcoming'
        WHEN substr(ends_at, 1, 10) < date('now') THEN 'past'
        ELSE 'open'
    END
    WHERE source = 'unstop'
""")
print(f"unstop statuses recomputed: {cur.rowcount}")
conn.commit()

for row in conn.execute("""
    SELECT source, status, COUNT(*) FROM hackathons GROUP BY source, status ORDER BY 1,2
"""):
    print(row)
conn.close()
