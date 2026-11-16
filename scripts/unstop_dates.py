import sqlite3

conn = sqlite3.connect("internships.db")

cur = conn.execute("""
    UPDATE hackathons SET ends_at = reg_ends_at
    WHERE source = 'unstop' AND ends_at IS NULL AND reg_ends_at IS NOT NULL
""")
print(f"ends_at backfilled: {cur.rowcount}")

# drop test listings
cur = conn.execute("DELETE FROM hackathons WHERE LOWER(TRIM(name)) = 'dummy'")
print(f"dummy rows removed: {cur.rowcount}")

conn.commit()

print("\n--- open vs expired (unstop) ---")
for row in conn.execute("""
    SELECT CASE WHEN ends_at >= datetime('now') THEN 'open' ELSE 'expired' END AS state,
           COUNT(*)
    FROM hackathons WHERE source='unstop' GROUP BY state
"""):
    print(row)

print("\n--- open, in person, Mumbai ---")
for row in conn.execute("""
    SELECT name, city, substr(ends_at,1,10) FROM hackathons
    WHERE source='unstop' AND is_online=0 AND LOWER(city) LIKE '%mumbai%'
      AND ends_at >= datetime('now')
    ORDER BY ends_at LIMIT 15
"""):
    print(row)
conn.close()
