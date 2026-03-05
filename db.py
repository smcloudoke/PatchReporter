import json
import os
import sqlite3

from constants import ALL_CATEGORIES, CUSTOMERS_FILE, DB_FILE, DEFAULT_FILTERS


# ─── Connection ───────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─── Schema ───────────────────────────────────────────────────────────────────

def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name    TEXT    NOT NULL,
                emails          TEXT    NOT NULL DEFAULT '',
                policy_schedule TEXT    NOT NULL DEFAULT '',
                last_updated    TEXT    NOT NULL DEFAULT '',
                filters         TEXT    NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS kb_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                category    TEXT    NOT NULL,
                kb          TEXT    NOT NULL,
                title       TEXT    NOT NULL
            );
        """)
        # Additive migration — safe for existing DBs that predate the filters column
        try:
            conn.execute("ALTER TABLE customers ADD COLUMN filters TEXT NOT NULL DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass  # Column already exists
    _migrate_from_json()


# ─── JSON migration (one-time) ────────────────────────────────────────────────

def _migrate_from_json():
    if not os.path.exists(CUSTOMERS_FILE):
        return

    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if count > 0:
            return  # DB already populated — skip

    try:
        with open(CUSTOMERS_FILE, "r", encoding="utf-8") as f:
            customers = json.load(f)
        for customer in customers:
            save_customer(customer)
        os.rename(CUSTOMERS_FILE, CUSTOMERS_FILE + ".migrated")
    except Exception:
        pass  # Never block startup due to a failed migration


# ─── Read ─────────────────────────────────────────────────────────────────────

def load_customers() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, company_name, emails, policy_schedule, last_updated, filters "
            "FROM customers ORDER BY id"
        ).fetchall()

        result = []
        for row in rows:
            customer = dict(row)
            customer["filters"] = _parse_filters(customer.get("filters", ""))
            customer["updates"] = _load_kb_entries(row["id"], conn)
            result.append(customer)
        return result


def _parse_filters(raw: str) -> dict:
    """Deserialise the filters JSON column, falling back to DEFAULT_FILTERS."""
    try:
        parsed = json.loads(raw) if raw else {}
        if not isinstance(parsed, dict):
            return dict(DEFAULT_FILTERS)
        return {**DEFAULT_FILTERS, **parsed}
    except (json.JSONDecodeError, TypeError):
        return dict(DEFAULT_FILTERS)


def _load_kb_entries(customer_id: int, conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT category, kb, title FROM kb_entries "
        "WHERE customer_id = ? ORDER BY category, kb",
        (customer_id,),
    ).fetchall()

    updates = {cat: [] for cat in ALL_CATEGORIES}
    for row in rows:
        if row["category"] in updates:
            updates[row["category"]].append({"kb": row["kb"], "title": row["title"]})
    return updates


# ─── Write ────────────────────────────────────────────────────────────────────

def save_customer(customer: dict) -> int:
    """Insert a new customer. Returns the assigned database id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO customers (company_name, emails, policy_schedule, last_updated, filters) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                customer.get("company_name", ""),
                customer.get("emails", ""),
                customer.get("policy_schedule", ""),
                customer.get("last_updated", ""),
                json.dumps(customer.get("filters", DEFAULT_FILTERS)),
            ),
        )
        new_id = cur.lastrowid
        _write_kb_entries(new_id, customer.get("updates", {}), conn)
    return new_id


def update_customer(customer: dict):
    """Update an existing customer record identified by customer['id']."""
    cid = customer["id"]
    with _connect() as conn:
        conn.execute(
            "UPDATE customers "
            "SET company_name=?, emails=?, policy_schedule=?, last_updated=?, filters=? "
            "WHERE id=?",
            (
                customer.get("company_name", ""),
                customer.get("emails", ""),
                customer.get("policy_schedule", ""),
                customer.get("last_updated", ""),
                json.dumps(customer.get("filters", DEFAULT_FILTERS)),
                cid,
            ),
        )
        conn.execute("DELETE FROM kb_entries WHERE customer_id=?", (cid,))
        _write_kb_entries(cid, customer.get("updates", {}), conn)


def delete_customer(customer_id: int):
    """Delete a customer and all their KB entries (cascade)."""
    with _connect() as conn:
        conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))


# ─── Private helpers ──────────────────────────────────────────────────────────

def _write_kb_entries(customer_id: int, updates: dict, conn: sqlite3.Connection):
    for category, entries in updates.items():
        for entry in entries:
            conn.execute(
                "INSERT INTO kb_entries (customer_id, category, kb, title) "
                "VALUES (?, ?, ?, ?)",
                (customer_id, category, entry.get("kb", ""), entry.get("title", "")),
            )
