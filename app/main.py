import os
import re
import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)

NAME_RE = re.compile(r"^[a-z]+$")
DB_PATH = os.getenv("DB_PATH", "/data/store.db")


def _err(status: int, code: str, message: str, details=None):
    payload = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return jsonify(payload), status


def _validate_name(field: str, value: str):
    if value is None or value == "":
        return False, f"Missing '{field}'"
    if not NAME_RE.match(value):
        return False, f"Invalid '{field}': lowercase letters only"
    return True, None


def _conn():
    # check_same_thread=False כי Gunicorn/Flask יכולים לטפל בכמה threads
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as con:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("""
            CREATE TABLE IF NOT EXISTS groceries (
                user_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                PRIMARY KEY (user_id, product_name)
            );
        """)


_init_db()


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True}), 200


@app.get("/get_product_amount")
def get_product_amount():
    product_name = request.args.get("product_name", type=str)
    ok, msg = _validate_name("product_name", product_name)
    if not ok:
        return _err(400, "INVALID_ARGUMENT", msg)

    with _conn() as con:
        row = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS users_count "
            "FROM groceries WHERE product_name = ? AND amount IS NOT NULL",
            (product_name,),
        ).fetchone()

    if row["users_count"] == 0:
        return _err(404, "NOT_FOUND", "Product not found", {"product_name": product_name})

    return jsonify({
        "ok": True,
        "data": {
            "product_name": product_name,
            "total_amount": int(row["total"]),
            "users_count": int(row["users_count"]),
        }
    }), 200


@app.post("/write")
def write():
    if not request.is_json:
        return _err(400, "INVALID_ARGUMENT", "Content-Type must be application/json")
    body = request.get_json(silent=True) or {}

    user_id = body.get("user_id")
    product_name = body.get("product_name")
    amount = body.get("amount")

    ok, msg = _validate_name("user_id", user_id)
    if not ok:
        return _err(400, "INVALID_ARGUMENT", msg)
    ok, msg = _validate_name("product_name", product_name)
    if not ok:
        return _err(400, "INVALID_ARGUMENT", msg)

    if amount is None:
        return _err(400, "INVALID_ARGUMENT", "Missing 'amount'")
    if not isinstance(amount, int):
        return _err(400, "INVALID_ARGUMENT", "'amount' must be an integer")
    if amount < 0:
        return _err(400, "INVALID_ARGUMENT", "'amount' must be >= 0")

    with _conn() as con:
        con.execute(
            "INSERT INTO groceries(user_id, product_name, amount) VALUES(?,?,?) "
            "ON CONFLICT(user_id, product_name) DO UPDATE SET amount=excluded.amount",
            (user_id, product_name, amount),
        )
        row = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS users_count "
            "FROM groceries WHERE product_name = ?",
            (product_name,),
        ).fetchone()

    return jsonify({
        "ok": True,
        "data": {
            "user_id": user_id,
            "written": [{"product_name": product_name, "amount": amount}],
            "product_total": {
                "product_name": product_name,
                "total_amount": int(row["total"]),
                "users_count": int(row["users_count"]),
            }
        }
    }), 200


@app.delete("/delete_product")
def delete_product():
    user_id = request.args.get("user_id", type=str)
    product_name = request.args.get("product_name", type=str)

    ok, msg = _validate_name("user_id", user_id)
    if not ok:
        return _err(400, "INVALID_ARGUMENT", msg)
    ok, msg = _validate_name("product_name", product_name)
    if not ok:
        return _err(400, "INVALID_ARGUMENT", msg)

    with _conn() as con:
        cur = con.execute(
            "DELETE FROM groceries WHERE user_id=? AND product_name=?",
            (user_id, product_name),
        )
        deleted = cur.rowcount

    if deleted == 0:
        return _err(404, "NOT_FOUND", "Product not found for user",
                    {"user_id": user_id, "product_name": product_name})

    return jsonify({
        "ok": True,
        "data": {"user_id": user_id, "product_name": product_name, "deleted": True}
    }), 200