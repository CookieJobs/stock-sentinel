"""DB 迁移 — 添加 sector 列"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "data" / "sentinel.db"
db = sqlite3.connect(str(DB))
cur = db.cursor()
cur.execute('PRAGMA table_info(stocks)')
cols = [r[1] for r in cur.fetchall()]
if 'sector' not in cols:
    cur.execute('ALTER TABLE stocks ADD COLUMN sector TEXT')
    print('+ sector 列已添加')
else:
    print('= sector 列已存在')
db.commit()
db.close()
print('迁移完成')
