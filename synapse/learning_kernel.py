"""SELF-LEARNING KERNEL (SLK) - The Memory of SYNAPSE.

Verantwortung laut Konzept:
- Speicherung jeder Entscheidung (Clip-Auswahl, Timing) in der Experience Database.
- Berechnung und Speicherung des Rewards (R) für jede Entscheidung.
- Bereitstellung der 'besten' Clips basierend auf Energie-Level und historischem Erfolg.
- Ermöglicht das Lernen über Projekte hinweg (Cross-Project Knowledge).
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).parent
DB_PATH = _HERE / "experience_omega.db"

class LearningKernel:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        """Initialisiert die SQLite-Tabelle für Erfahrungen."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS experiences (
                uuid TEXT PRIMARY KEY,
                track_hash TEXT,
                clip_id TEXT,
                energy_level REAL,
                reward REAL,
                metadata TEXT,
                timestamp TEXT
            )
        ''')
        self.conn.commit()

    def save_experience(self, track_hash: str, clip_id: str, energy: float,
                        reward: float, metadata: dict[str, Any]) -> str:
        """Speichert eine getroffene Entscheidung und ihren Erfolg. [5]"""
        uid = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO experiences (uuid, track_hash, clip_id, energy_level, reward, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (uid, track_hash, clip_id, energy, reward, str(metadata), 
              datetime.now(timezone.utc).isoformat()))
        self.conn.commit()
        return uid

    def get_best_clip(self, track_hash: str | None = None, energy: float = 0.5,
                      tolerance: float = 0.2) -> Optional[str]:
        """
        Abfrage erfolgreicher Schemata aus der Vergangenheit [6].
        Sucht nach Clips, die bei ähnlichem Energie-Level einen hohen Reward erzielten.
        """
        cursor = self.conn.cursor()
        # Wenn track_hash None ist, sucht das System global über alle Songs (General Knowledge)
        if track_hash:
            query = "SELECT clip_id FROM experiences WHERE track_hash = ? AND ABS(energy_level - ?) < ? ORDER BY reward DESC LIMIT 1"
            cursor.execute(query, (track_hash, energy, tolerance))
        else:
            query = "SELECT clip_id FROM experiences WHERE ABS(energy_level - ?) < ? ORDER BY reward DESC LIMIT 1"
            cursor.execute(query, (energy, tolerance))
            
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_experiences(self) -> list[dict]:
        """Gibt alle Erfahrungen zur Analyse an den Evolution Manager zurück."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM experiences ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

# Singleton-Instanz für den globalen Zugriff
slk = LearningKernel()
