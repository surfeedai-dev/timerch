import time
import sqlite3
from pathlib import Path
from datetime import date


class TimeTracker:
    def __init__(self, hourly_rate: int = 10320):
        self.hourly_rate = hourly_rate
        self.start_time = time.time()
        self.db_path = Path(__file__).parent / "data" / "sessions.db"
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    duration_seconds INTEGER,
                    earnings INTEGER
                )
            """)

    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def earnings(self) -> float:
        return (self.elapsed_seconds() / 3600) * self.hourly_rate

    def format_time(self) -> str:
        s = int(self.elapsed_seconds())
        h, m, s = s // 3600, (s % 3600) // 60, s % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def format_earnings(self) -> str:
        return f"{int(self.earnings()):,}원"

    def save_session(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (date, duration_seconds, earnings) VALUES (?, ?, ?)",
                (date.today().isoformat(), int(self.elapsed_seconds()), int(self.earnings()))
            )
