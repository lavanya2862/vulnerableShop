"""SQLite connection handling, schema creation and fictional seed data."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price REAL NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
"""

# All records are fictional. Emails use the reserved .test TLD.
SEED_USERS = [
    ("Alice Example", "alice@shop.test"),
    ("Bob Sample", "bob@shop.test"),
    ("Carol Demo", "carol@shop.test"),
]

SEED_PRODUCTS = [
    ("Aurora Phone X", "Fictional smartphone with a 6.1 inch display", 699.00, 25),
    ("Nimbus Headphones", "Wireless over-ear headphones for phone and laptop", 149.99, 40),
    ("Quartz Laptop 14", "Lightweight 14 inch laptop", 1099.00, 10),
    ("Pebble Phone Case", "Silicone case for the Aurora Phone X", 19.99, 200),
    ("Orbit Smartwatch", "Fitness tracking smartwatch", 249.50, 30),
]

# (user_id, product_id, quantity, status)
SEED_ORDERS = [
    (1, 1, 1, "shipped"),
    (1, 4, 2, "delivered"),
    (2, 3, 1, "pending"),
    (3, 2, 1, "shipped"),
    (3, 5, 1, "pending"),
]


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.executemany("INSERT INTO users (name, email) VALUES (?, ?)", SEED_USERS)
        if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)",
                SEED_PRODUCTS,
            )
        if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO orders (user_id, product_id, quantity, status) VALUES (?, ?, ?, ?)",
                SEED_ORDERS,
            )
