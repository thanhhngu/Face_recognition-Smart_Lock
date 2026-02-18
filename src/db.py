import os
import mysql.connector
from dotenv import load_dotenv
import json

from typing import List, Tuple

# Load .env from project root (one level above src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    database=os.getenv("DB_NAME")
)
cursor = conn.cursor()


def get_or_create_user(name: str) -> int:
    """Return user id for `name`, creating a user row if needed."""
    cursor.execute("SELECT id FROM users WHERE name = %s", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO users (name) VALUES (%s)", (name,))
    conn.commit()
    return cursor.lastrowid


def insert_encodings(user_id: int, encodings: List[List[float]]):
    """Insert one or more encodings (list of float lists) for `user_id`.
    Each encoding is stored as JSON in the `encoding` column.
    """
    sql = "INSERT INTO face_encodings (user_id, encoding) VALUES (%s, %s)"
    data = []
    for enc in encodings:
        # ensure plain python floats
        arr = [float(x) for x in list(enc)]
        data.append((user_id, json.dumps(arr)))
    cursor.executemany(sql, data)
    conn.commit()


def count_encodings_for_user(user_id: int) -> int:
    cursor.execute("SELECT COUNT(*) FROM face_encodings WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def delete_oldest_encodings(user_id: int, keep_count: int):
    """Delete oldest encodings so that only keep_count most recent remain for user_id."""
    cursor.execute("SELECT id FROM face_encodings WHERE user_id = %s ORDER BY id", (user_id,))
    rows = cursor.fetchall()
    ids = [r[0] for r in rows]
    if len(ids) <= keep_count:
        return
    # delete older ids
    to_delete = ids[:-keep_count]
    sql = f"DELETE FROM face_encodings WHERE id IN ({','.join(['%s']*len(to_delete))})"
    cursor.execute(sql, tuple(to_delete))
    conn.commit()


def fetch_all_encodings_with_names() -> Tuple[List[List[float]], List[str]]:
    """Return (encodings, names) where encodings is list of float lists and names matched by index."""
    sql = "SELECT fe.encoding, u.name FROM face_encodings fe JOIN users u ON fe.user_id = u.id ORDER BY fe.id"
    cursor.execute(sql)
    rows = cursor.fetchall()
    encs = []
    names = []
    for encoding_json, name in rows:
        try:
            arr = json.loads(encoding_json) if isinstance(encoding_json, str) else encoding_json
            encs.append([float(x) for x in arr])
            names.append(name)
        except Exception:
            continue
    return encs, names

def user_exists(name):
    cursor.execute("SELECT id FROM users WHERE name=%s", (name,))
    return cursor.fetchone() is not None