"""A searchable catalogue of files."""
from __future__ import annotations

import sqlite3


class Catalogue:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        conn.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL)")

    def add(self, owner: str, name: str) -> int:
        """Store a file of `owner`; returns the new row id."""
        if not owner.strip() or not name.strip():
            raise ValueError("owner and name must not be blank")
        cursor = self._conn.execute("INSERT INTO files (owner, name) VALUES (?, ?)", (owner, name))
        return int(cursor.lastrowid)

    def find(self, owner: str, text: str) -> list[str]:
        """Names of `owner`'s files that contain `text`, ignoring case, sorted."""
        rows = self._conn.execute("SELECT name FROM files WHERE owner = ?", (owner,)).fetchall()
        needle = text.lower()
        return sorted(name for (name,) in rows if needle in name.lower())
