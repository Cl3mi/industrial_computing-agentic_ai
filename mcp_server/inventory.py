"""SQLite product inventory. Writes happen only in init_db; every query uses a read-only connection."""

import sqlite3
from pathlib import Path

SEED = [
    ("BRG-6204", "Deep-groove ball bearing 6204", 1200, 3.40, "Nordlager GmbH"),
    ("BRG-6305", "Deep-groove ball bearing 6305", 640, 5.10, "Nordlager GmbH"),
    ("HYD-SEAL-40", "Hydraulic piston seal 40 mm", 35, 12.80, "Hydrotec AG"),
    ("HYD-HOSE-2M", "Hydraulic hose 2 m, 1/2 inch", 18, 48.50, "Hydrotec AG"),
    ("MOT-24V-200", "DC motor 24 V 200 W", 42, 129.00, "Voltwerk"),
    ("SNS-IND-M12", "Inductive proximity sensor M12", 310, 21.90, "Sensorik Tirol"),
    ("BLT-V-A38", "V-belt A38", 95, 7.25, "Antrieb & Co"),
    ("FLT-AIR-C7", "Cabinet air filter mat C7", 420, 4.60, "Klimatec"),
]


def connect_ro(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS parts ("
            "sku TEXT PRIMARY KEY, name TEXT NOT NULL, stock INTEGER NOT NULL, "
            "unit_price REAL NOT NULL, supplier TEXT NOT NULL)"
        )
        if conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 0:
            conn.executemany("INSERT INTO parts VALUES (?, ?, ?, ?, ?)", SEED)
        conn.commit()
    finally:
        conn.close()


def lookup_inventory(db_path, query: str, limit: int = 10) -> list[dict]:
    like = f"%{query}%"
    conn = connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT sku, name, stock, unit_price, supplier FROM parts "
            "WHERE sku LIKE ? OR name LIKE ? OR supplier LIKE ? ORDER BY sku LIMIT ?",
            (like, like, like, limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def list_low_stock(db_path, threshold: int = 50) -> list[dict]:
    conn = connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT sku, name, stock, unit_price, supplier FROM parts WHERE stock < ? ORDER BY stock",
            (threshold,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
