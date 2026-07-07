import sqlite3
import sys

db_path = '/home/az001a/Script/media_server/data/general.db'
conn = sqlite3.connect(db_path)
rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
for r in rows:
    print(f"  {r[0]} = {repr(r[1])}")
conn.close()
