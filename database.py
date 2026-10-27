"""SQLite persistence layer; one connection per operation for Streamlit safety."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .pdf_parser import ParsedPaper


class PaperStore:
    def __init__(self, db_path: str | Path = "data/papers.db"):
        self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL DEFAULT '',
                    page_count INTEGER NOT NULL,
                    full_text TEXT NOT NULL,
                    sections_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    text TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id);
            """)

    def list_papers(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, filename, title, author, page_count, tags, notes, created_at FROM papers ORDER BY created_at DESC, id DESC").fetchall()
            return [dict(row) for row in rows]

    def get_paper(self, paper_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["sections"] = json.loads(result.pop("sections_json"))
            result["summary"] = json.loads(result.pop("summary_json"))
            result["chunks"] = [dict(r) for r in conn.execute("SELECT chunk_index AS chunk_id, page_number, text FROM chunks WHERE paper_id = ? ORDER BY chunk_index", (paper_id,))]
            return result

    def save_paper(self, fingerprint: str, filename: str, paper: ParsedPaper, sections: dict[str, Any], summary: dict[str, str], tags: str = "", notes: str = "") -> int:
        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM papers WHERE fingerprint = ?", (fingerprint,)).fetchone()
            if existing:
                raise ValueError("This PDF has already been added to your library.")
            cursor = conn.execute("""INSERT INTO papers(fingerprint, filename, title, author, subject, page_count, full_text, sections_json, summary_json, tags, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fingerprint, filename, paper.title, paper.author, paper.subject, paper.page_count, paper.full_text, json.dumps(sections, ensure_ascii=False), json.dumps(summary, ensure_ascii=False), tags, notes))
            paper_id = int(cursor.lastrowid)
            conn.executemany("INSERT INTO chunks(paper_id, chunk_index, page_number, text) VALUES (?, ?, ?, ?)", [(paper_id, c.chunk_id, c.page_number, c.text) for c in paper.chunks])
            return paper_id

    def update_details(self, paper_id: int, tags: str, notes: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("UPDATE papers SET tags = ?, notes = ? WHERE id = ?", (tags, notes, paper_id))
            if cursor.rowcount == 0:
                raise KeyError("Paper not found")

    def delete_paper(self, paper_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))

    def search_chunks(self, paper_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT chunk_index AS chunk_id, page_number, text FROM chunks WHERE paper_id = ? ORDER BY chunk_index", (paper_id,))]
