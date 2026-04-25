import pymysql
import pymysql.cursors
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME


def get_db():
    """Return a new database connection with DictCursor."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset='utf8mb4',
        autocommit=False,
    )


def query(sql, args=None, one=False, commit=False):
    """
    Execute a SQL statement and return results.
    - one=True  → return a single row dict (or None)
    - commit=True → commit after execution (for INSERT/UPDATE/DELETE)
    Returns (rows, lastrowid) for write queries, rows for reads.
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            if commit:
                conn.commit()
                return cur.lastrowid
            result = cur.fetchone() if one else cur.fetchall()
            return result
    finally:
        conn.close()
