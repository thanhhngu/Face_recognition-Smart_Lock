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

def verify_key(key: str) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM key_devices WHERE api_key = %s", (key,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def verify_user_credentials(email: str, password_hash: str) -> str:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT api_key FROM account WHERE email = %s AND password_hash = %s", (email, password_hash))
        row = cursor.fetchone()
        if row:
            return row[0] 
        return None
    finally:
        cursor.close()

def user_exists(name: str, key: str) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE name=%s AND api_key=%s", (name, key))
        return cursor.fetchone() is not None
    finally:
        cursor.close()

def create_user(name: str, key: str) -> int:
    """Create a new user and return their ID."""
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (name, api_key) VALUES (%s, %s)", (name, key))
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()

def get_user_id(name: str, key: str) -> int:
    """Return user id for `name`, or None if not found."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE name = %s AND api_key = %s", (name, key))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()

def insert_encodings(user_id: int, encodings: List[List[float]]):
    """Insert one or more encodings (list of float lists) for `user_id`.
    Each encoding is stored as JSON in the `encoding` column.
    """
    cursor = conn.cursor()
    try:
        sql = "INSERT INTO face_encodings (user_id, encoding) VALUES (%s, %s)"
        data = []
        for enc in encodings:
            # ensure plain python floats
            arr = [float(x) for x in list(enc)]
            data.append((user_id, json.dumps(arr)))
        cursor.executemany(sql, data)
        conn.commit()
    finally:
        cursor.close()


def count_encodings_for_user(user_id: int) -> int:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM face_encodings WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    finally:
        cursor.close()


def delete_oldest_encodings(user_id: int, keep_count: int):
    """Delete oldest encodings so that only keep_count most recent remain for user_id."""
    cursor = conn.cursor()
    try:
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
    finally:
        cursor.close()


def fetch_all_encodings_with_names(key: str) -> Tuple[List[List[float]], List[str]]:
    """Return (encodings, names) where encodings is list of float lists and names matched by index."""
    cursor = conn.cursor()
    try:
        sql = "SELECT fe.encoding, u.name FROM face_encodings fe JOIN users u ON fe.user_id = u.id WHERE u.api_key = %s ORDER BY fe.id"
        cursor.execute(sql, (key,))
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
    finally:
        cursor.close()

def log_access_attempt(user_id: int, success: bool):
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO access_logs (user_id, success) VALUES (%s, %s)", (user_id, success))
        conn.commit()
    finally:
        cursor.close()
    
def fetch_access_logs(key: str) -> List[Tuple[str, str, bool]]:
    """Return list of (user_name, access_time, success) tuples for access logs."""
    cursor = conn.cursor()
    try:
        sql = """
        SELECT u.name, al.access_time, al.success 
        FROM access_logs al 
        LEFT JOIN users u ON al.user_id = u.id
        where u.api_key = %s 
        ORDER BY al.access_time DESC
        """
        cursor.execute(sql, (key,))
        rows = cursor.fetchall()
        return [(row[0] if row[0] else "Unknown", row[1].strftime("%Y-%m-%d %H:%M:%S"), bool(row[2])) for row in rows]
    finally:
        cursor.close()
'''
def init_db():
    # Tạo database nếu chưa có
    cursor.execute("CREATE DATABASE IF NOT EXISTS smart_lock")
    cursor.execute("USE smart_lock")

    # Tạo bảng users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        role VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tạo bảng face_encodings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS face_encodings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        encoding JSON NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)
    conn.commit()

# Gọi init_db khi khởi động
init_db()
'''