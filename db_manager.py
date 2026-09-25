import sqlite3
import threading

class DBManager:
    """إدارة قاعدة البيانات المحلية SQLite لحفظ سجل المحادثات والرسائل"""
    def __init__(self, db_name="latal_local.db"):
        self.db_name = db_name
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT,
                    sender TEXT,
                    message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()

    def save_message(self, room, sender, message):
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO messages (room, sender, message) VALUES (?, ?, ?)", (room, sender, message))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[DB ERROR] {e}")

    def get_messages(self, room="Broadcast", limit=50):
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                cursor.execute("SELECT sender, message, timestamp FROM messages WHERE room = ? ORDER BY id ASC LIMIT ?", (room, limit))
                rows = cursor.fetchall()
                conn.close()
                return rows
            except Exception:
                return []