import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sns_sensing", "data", "trend_data.db")
conn = sqlite3.connect(db_path)
conn.execute("DELETE FROM api_cache")
conn.commit()
conn.close()
print("Cache successfully cleared using sqlite3!")
