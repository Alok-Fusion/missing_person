"""
db.py  ·  SQLite helpers for Missing‑Person Finder
– auto‑creates / auto‑migrates tables on import
– SHA‑256 password hashing (demo only; use salted hash in prod)
"""
from __future__ import annotations

import hashlib
import sqlite3
from typing import List, Tuple

import numpy as np
import pandas as pd

DB_PATH = "missing.db"
ACCESS_CODE = "FIND2025"  # shared access gate‑code


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hash(pw: str) -> str:
    """Return SHA‑256 hash (hex)."""
    return hashlib.sha256(pw.encode()).hexdigest()


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


# ─────────────────────────────────────────────────────────────────────────────
# Schema bootstrap + lightweight migrations
# ─────────────────────────────────────────────────────────────────────────────

def create_tables() -> None:
    """Create base tables and add any missing columns (idempotent migrations)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1) users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL
        );
        """
    )

    # 2) persons table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS persons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            age         INTEGER,
            gender      TEXT,
            loc         TEXT,
            date        TEXT,
            notes       TEXT,
            photo_path  TEXT,
            embedding   BLOB,
            created_by  INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );
        """
    )

    # Add new optional columns if missing
    new_cols = [
        ("gps_lat", "REAL"),
        ("gps_lon", "REAL"),
        ("address", "TEXT"),
        ("contact_name", "TEXT"),
        ("contact_number", "TEXT"),
        ("aadhaar_number", "TEXT"),
        ("relation", "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if not _column_exists(cur, "persons", col_name):
            cur.execute(f"ALTER TABLE persons ADD COLUMN {col_name} {col_type}")

    # 3) found_persons table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS found_persons AS SELECT * FROM persons WHERE 0;
        """
    )
    for col_name, col_type in new_cols:
        if not _column_exists(cur, "found_persons", col_name):
            cur.execute(f"ALTER TABLE found_persons ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# User management
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username: str, password: str) -> bool:
    """Return True if user created, False if username already taken."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, _hash(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_user(username: str, password: str) -> int | None:
    """Return user_id if credentials valid else None."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT id, password FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if row and row[1] == _hash(password):
        return row[0]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Missing‑person records
# ─────────────────────────────────────────────────────────────────────────────

def add_person(data: dict, embedding: np.ndarray, user_id: int) -> None:
    """Insert a new missing‑person record."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO persons
        (name, age, gender, loc, gps_lat, gps_lon, date,
         notes, photo_path, embedding, address, contact_name,
         contact_number, aadhaar_number, relation, created_by)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data.get("name"),
            data.get("age"),
            data.get("gender"),
            data.get("loc"),
            data.get("gps_lat"),
            data.get("gps_lon"),
            data.get("date"),
            data.get("notes"),
            data.get("photo_path"),
            embedding.astype(np.float32).tobytes(),
            data.get("address"),
            data.get("contact_name"),
            data.get("contact_number"),
            data.get("aadhaar_number"),
            data.get("relation"),
            user_id,
        ),
    )
    conn.commit()
    conn.close()


def all_persons() -> List[Tuple]:
    """Return all unresolved cases (id, name, …, embedding)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT id, name, age, gender, photo_path, loc,
            gps_lat, gps_lon, embedding
        FROM persons
        """
    ).fetchall()
    conn.close()
    return rows


def get_user_cases(user_id: int) -> pd.DataFrame:
    """Return all active cases for the given user, including photo_path for UI."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT id, name, age, gender,
            loc, gps_lat, gps_lon, date, notes,
            address, contact_name, contact_number,
            aadhaar_number, relation, photo_path
        FROM persons
        WHERE created_by = ?
        ORDER BY date DESC
        """,
        conn,
        params=(user_id,),
    )
    conn.close()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Mark person as found
# ─────────────────────────────────────────────────────────────────────────────

def mark_person_as_found(person_id: int) -> None:
    """Move a record from 'persons' to 'found_persons' and delete the original."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
        row = cur.fetchone()
        if row:
            cur.execute("INSERT INTO found_persons SELECT * FROM persons WHERE id = ?", (person_id,))
            cur.execute("DELETE FROM persons WHERE id = ?", (person_id,))
        conn.commit()

def delete_found_person(person_id: int) -> None:
    """Permanently delete a record from found_persons table."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM found_persons WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Auto-run setup
# ─────────────────────────────────────────────────────────────────────────────

create_tables()
