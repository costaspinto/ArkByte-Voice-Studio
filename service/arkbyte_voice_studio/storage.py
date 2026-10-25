from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Storage:
    """Small local SQLite store. All SQL uses bound parameters."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                language TEXT NOT NULL,
                reference_path TEXT NOT NULL,
                source_name TEXT NOT NULL,
                consent_ack INTEGER NOT NULL CHECK(consent_ack IN (0,1)),
                created_at TEXT NOT NULL
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS history (
                id TEXT PRIMARY KEY,
                profile_id TEXT,
                profile_name TEXT NOT NULL,
                script_preview TEXT NOT NULL,
                language TEXT NOT NULL,
                output_path TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE SET NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC)")
            conn.execute("""CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                script TEXT NOT NULL,
                profile_id TEXT,
                language_id TEXT NOT NULL,
                output_name TEXT NOT NULL,
                exaggeration REAL NOT NULL DEFAULT 0.5,
                cfg_weight REAL NOT NULL DEFAULT 0.5,
                temperature REAL NOT NULL DEFAULT 0.8,
                model_id TEXT NOT NULL DEFAULT 'chatterbox',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE SET NULL
            )""")
            project_columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()}
            if "model_id" not in project_columns:
                conn.execute("ALTER TABLE projects ADD COLUMN model_id TEXT NOT NULL DEFAULT 'chatterbox'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC)")
            conn.execute("""CREATE TABLE IF NOT EXISTS voice_samples (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                original_path TEXT NOT NULL,
                model_reference_path TEXT NOT NULL,
                source_name TEXT NOT NULL,
                transcript TEXT NOT NULL DEFAULT '',
                transcript_reviewed INTEGER NOT NULL DEFAULT 0 CHECK(transcript_reviewed IN (0,1)),
                analysis_json TEXT NOT NULL,
                is_anchor INTEGER NOT NULL DEFAULT 0 CHECK(is_anchor IN (0,1)),
                created_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            )""")
            sample_columns = {row["name"] for row in conn.execute("PRAGMA table_info(voice_samples)").fetchall()}
            if "transcript_reviewed" not in sample_columns:
                conn.execute("ALTER TABLE voice_samples ADD COLUMN transcript_reviewed INTEGER NOT NULL DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_samples_profile ON voice_samples(profile_id, created_at)")
            conn.execute("""CREATE TABLE IF NOT EXISTS voice_profile_meta (
                profile_id TEXT PRIMARY KEY,
                accent_notes TEXT NOT NULL DEFAULT '',
                pronunciation_notes TEXT NOT NULL DEFAULT '',
                analysis_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS pronunciation_entries (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                term TEXT NOT NULL,
                say_as TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                UNIQUE(profile_id, term)
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pronunciations_profile ON pronunciation_entries(profile_id, term)")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def add_profile(self, profile: dict[str, Any]) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO profiles(id,name,language,reference_path,source_name,consent_ack,created_at) VALUES(?,?,?,?,?,?,?)",
                (profile["id"], profile["name"], profile["language"], profile["reference_path"],
                 profile["source_name"], int(profile["consent_ack"]), self._now()),
            )

    def list_profiles(self) -> list[dict[str, Any]]:
        with self._lock, self._connection() as conn:
            rows = conn.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
            return dict(row) if row else None

    def set_profile_reference(self, profile_id: str, reference_path: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("UPDATE profiles SET reference_path=? WHERE id=?", (reference_path, profile_id))

    def delete_profile(self, profile_id: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))

    def add_history(self, item: dict[str, Any]) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO history(id,profile_id,profile_name,script_preview,language,output_path,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (item["id"], item.get("profile_id"), item["profile_name"], item["script_preview"],
                 item["language"], item["output_path"], item.get("status", "complete"), self._now()),
            )

    def list_history(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock, self._connection() as conn:
            rows = conn.execute("SELECT * FROM history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]


    def save_project(self, project: dict[str, Any]) -> dict[str, Any]:
        """Create or update a local narration project and return its persisted row."""
        now = self._now()
        project_id = project["id"]
        with self._lock, self._connection() as conn:
            existing = conn.execute(
                "SELECT created_at FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """INSERT INTO projects(
                    id,title,script,profile_id,language_id,output_name,
                    exaggeration,cfg_weight,temperature,model_id,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    script=excluded.script,
                    profile_id=excluded.profile_id,
                    language_id=excluded.language_id,
                    output_name=excluded.output_name,
                    exaggeration=excluded.exaggeration,
                    cfg_weight=excluded.cfg_weight,
                    temperature=excluded.temperature,
                    model_id=excluded.model_id,
                    updated_at=excluded.updated_at""",
                (
                    project_id, project["title"], project["script"], project.get("profile_id"),
                    project["language_id"], project["output_name"], float(project["exaggeration"]),
                    float(project["cfg_weight"]), float(project["temperature"]), project.get("model_id", "chatterbox"), created_at, now,
                ),
            )
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row)

    def list_projects(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def list_project_summaries(self, limit: int = 200) -> list[dict[str, Any]]:
        """Read only the columns needed by the project library; do not load scripts."""
        limit = max(1, min(int(limit), 500))
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """SELECT id, title, substr(script, 1, 240) AS script_preview,
                          length(script) AS character_count, profile_id, language_id,
                          created_at, updated_at
                   FROM projects ORDER BY updated_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    def delete_project(self, project_id: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def add_voice_samples(self, samples: list[dict[str, Any]]) -> None:
        with self._lock, self._connection() as conn:
            for sample in samples:
                conn.execute(
                    """INSERT INTO voice_samples(
                        id,profile_id,original_path,model_reference_path,source_name,
                        transcript,transcript_reviewed,analysis_json,is_anchor,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (sample["id"], sample["profile_id"], sample["original_path"],
                     sample["model_reference_path"], sample["source_name"],
                     sample.get("transcript", ""), int(sample.get("transcript_reviewed", False)),
                     json.dumps(sample["analysis"]), int(sample.get("is_anchor", False)), self._now()),
                )

    def delete_voice_samples(self, profile_id: str, sample_ids: list[str]) -> None:
        """Remove a batch of samples belonging to a profile (used for rollback)."""
        if not sample_ids:
            return
        placeholders = ",".join("?" for _ in sample_ids)
        with self._lock, self._connection() as conn:
            conn.execute(
                f"DELETE FROM voice_samples WHERE profile_id=? AND id IN ({placeholders})",
                [profile_id, *sample_ids],
            )

    def list_voice_samples(self, profile_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM voice_samples WHERE profile_id=? ORDER BY is_anchor DESC, created_at ASC",
                (profile_id,),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["analysis"] = json.loads(item.pop("analysis_json"))
                result.append(item)
            return result

    def get_voice_sample(self, sample_id: str, profile_id: str | None = None) -> dict[str, Any] | None:
        with self._lock, self._connection() as conn:
            if profile_id:
                row = conn.execute("SELECT * FROM voice_samples WHERE id=? AND profile_id=?", (sample_id, profile_id)).fetchone()
            else:
                row = conn.execute("SELECT * FROM voice_samples WHERE id=?", (sample_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["analysis"] = json.loads(item.pop("analysis_json"))
            return item

    def update_voice_sample_transcript(self, profile_id: str, sample_id: str, transcript: str, reviewed: bool = True) -> None:
        with self._lock, self._connection() as conn:
            cursor = conn.execute(
                "UPDATE voice_samples SET transcript=?, transcript_reviewed=? WHERE id=? AND profile_id=?",
                (transcript, int(reviewed), sample_id, profile_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Sample does not belong to this voice profile")

    def set_profile_anchor(self, profile_id: str, sample_id: str) -> None:
        with self._lock, self._connection() as conn:
            exists = conn.execute("SELECT 1 FROM voice_samples WHERE id=? AND profile_id=?", (sample_id, profile_id)).fetchone()
            if not exists:
                raise ValueError("Sample does not belong to this voice profile")
            conn.execute("UPDATE voice_samples SET is_anchor=0 WHERE profile_id=?", (profile_id,))
            conn.execute("UPDATE voice_samples SET is_anchor=1 WHERE id=? AND profile_id=?", (sample_id, profile_id))

    def save_profile_analysis(self, profile_id: str, accent_notes: str, pronunciation_notes: str, analysis: dict[str, Any]) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                """INSERT INTO voice_profile_meta(profile_id,accent_notes,pronunciation_notes,analysis_json,updated_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET
                   accent_notes=excluded.accent_notes, pronunciation_notes=excluded.pronunciation_notes,
                   analysis_json=excluded.analysis_json, updated_at=excluded.updated_at""",
                (profile_id, accent_notes, pronunciation_notes, json.dumps(analysis), self._now()),
            )

    def get_profile_analysis(self, profile_id: str) -> dict[str, Any] | None:
        with self._lock, self._connection() as conn:
            row = conn.execute("SELECT * FROM voice_profile_meta WHERE profile_id=?", (profile_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["analysis"] = json.loads(item.pop("analysis_json"))
            return item

    def upsert_pronunciation(self, item: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connection() as conn:
            existing = conn.execute("SELECT id,created_at FROM pronunciation_entries WHERE profile_id=? AND term=?", (item["profile_id"], item["term"])).fetchone()
            entry_id = existing["id"] if existing else item["id"]
            created_at = existing["created_at"] if existing else self._now()
            conn.execute(
                """INSERT INTO pronunciation_entries(id,profile_id,term,say_as,notes,created_at)
                   VALUES(?,?,?,?,?,?) ON CONFLICT(profile_id,term) DO UPDATE SET
                   say_as=excluded.say_as, notes=excluded.notes""",
                (entry_id, item["profile_id"], item["term"], item["say_as"], item.get("notes", ""), created_at),
            )
            row = conn.execute("SELECT * FROM pronunciation_entries WHERE id=?", (entry_id,)).fetchone()
            return dict(row)

    def list_pronunciations(self, profile_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM pronunciation_entries WHERE profile_id=? ORDER BY term COLLATE NOCASE", (profile_id,)).fetchall()]

    def delete_pronunciation(self, profile_id: str, entry_id: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("DELETE FROM pronunciation_entries WHERE profile_id=? AND id=?", (profile_id, entry_id))

    def integrity_check(self) -> str:
        with self._lock, self._connection() as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return str(row[0])
