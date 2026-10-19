import sqlite3

import pytest

from mcp_server import inventory


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "inv.db"
    inventory.init_db(path)
    return path


def test_init_db_seeds_once(db):
    inventory.init_db(db)  # second call must not duplicate rows
    assert len(inventory.lookup_inventory(db, "", limit=100)) == len(inventory.SEED)


def test_lookup_by_sku_and_name(db):
    rows = inventory.lookup_inventory(db, "6204")
    assert rows[0]["sku"] == "BRG-6204"
    assert rows[0]["stock"] == 1200
    assert inventory.lookup_inventory(db, "hydraulic")[0]["sku"].startswith("HYD")


def test_lookup_is_not_injectable(db):
    assert inventory.lookup_inventory(db, "x'; DROP TABLE parts; --") == []
    assert len(inventory.lookup_inventory(db, "")) > 0  # table still exists


def test_lookup_respects_limit(db):
    assert len(inventory.lookup_inventory(db, "", limit=2)) == 2


def test_connection_is_read_only(db):
    with pytest.raises(sqlite3.OperationalError):
        inventory.connect_ro(db).execute("DELETE FROM parts")


def test_low_stock(db):
    rows = inventory.list_low_stock(db, threshold=50)
    assert rows and all(r["stock"] < 50 for r in rows)
    assert rows == sorted(rows, key=lambda r: r["stock"])
