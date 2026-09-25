"""
Koneksi ke Supabase Postgres.
PENTING: gunakan connection string dengan role yang HANYA punya privilege SELECT
(lihat sql/create_readonly_role.sql). Ini adalah lapisan pertahanan pertama.
Lapisan kedua ada di tools.py yang hanya membangun query SELECT terparameter,
tidak pernah menerima raw SQL dari LLM/user.
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ["SUPABASE_DB_URL"]
ALLOWED_TABLES = set(t.strip() for t in os.environ.get("ALLOWED_TABLES", "projects").split(","))

# execution_options read-only sebagai lapisan tambahan di level driver
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    execution_options={"postgresql_readonly": True},
)


@contextmanager
def get_conn():
    with engine.connect() as conn:
        # set transaksi read-only secara eksplisit di level session Postgres
        conn.execute(text("SET TRANSACTION READ ONLY"))
        yield conn


def assert_table_allowed(table: str):
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Tabel '{table}' tidak diizinkan diakses agent.")