import sqlite3
from datetime import datetime

conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

def init_db():
    # Połącz się z bazą (utworzy plik jeśli nie istnieje)
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()

    # Sprawdź czy tabela istnieje
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS status_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_name TEXT NOT NULL,
        person_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        date_add DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        date_add DATETIME DEFAULT CURRENT_TIMESTAMP,
        permissions TEXT NOT NULL DEFAULT '[]',
        approved_by_user_id INTEGER DEFAULT NULL,
        category TEXT DEFAULT "general"
    )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS status_unique_idx 
        ON status_requests (status);
    """)


    conn.commit()
    conn.close()

    print("✅ Database ready (table 'status_requests' checked or created)")

def get_all_statuses():
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM status_requests ORDER BY date_add DESC")
    rows = cursor.fetchall()

    conn.close()
    return rows

def add_status_request(person_name: str, person_id: int, status: str):
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO status_requests (person_name, person_id, status) VALUES (?, ?, ?)",
        (person_name, person_id, status)
    )

    conn.commit()
    conn.close()

def get_added_statuses_from_user(person_id: int):
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM status_requests WHERE person_id = ? ORDER BY date_add DESC",
        (person_id,)
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_permissions():
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM permissions ORDER BY date_add DESC")
    rows = cursor.fetchall()

    conn.close()
    return rows

def approve_status_by_value(status: str, approved_by_user_id: int):
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE status_requests SET approved_by_user_id = ? WHERE status = ?",
        (approved_by_user_id, status)
    )

    conn.commit()
    conn.close()

def get_status_by_category_and_user(category: str, person_id: int):
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM status_requests WHERE category = ? AND person_id = ? ORDER BY date_add DESC",
        (category, person_id)
    )
    rows = cursor.fetchall()

    conn.close()
    return rows

def get_approved_statuses():
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM status_requests WHERE approved_by_user_id IS NOT NULL ORDER BY date_add DESC"
    )
    rows = cursor.fetchall()

    conn.close()
    return rows

def get_statuses_by_category(category: str):
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM status_requests WHERE category = ? AND approved_by_user_id IS NOT NULL ORDER BY date_add DESC",
        (category,)
    )
    rows = cursor.fetchall()

    conn.close()
    return rows

def get_all_categories():
    conn = sqlite3.connect("bot_data.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT DISTINCT category FROM status_requests"
    )
    rows = cursor.fetchall()

    conn.close()
    return [row["category"] for row in rows]