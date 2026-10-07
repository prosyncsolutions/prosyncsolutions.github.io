"""
Notes API - login + text CRUD backend for a mobile app (sample project)

Stack: Flask, SQLite, JWT bearer tokens, salted password hashes.
Run:   pip install -r requirements.txt && python app.py
Test:  python -m unittest test_api.py -v
"""
import os, sqlite3, datetime, functools
import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

TOKEN_HOURS = 12


def create_app(db_path="notes.db", secret=None):
    app = Flask(__name__)
    app.config["DB"] = db_path
    app.config["SECRET"] = secret or os.environ.get("JWT_SECRET", "dev-only-change-me-in-production-0123456789")

    # ---------- database ----------
    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_):
        conn = g.pop("db", None)
        if conn: conn.close()

    with app.app_context():
        db().executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notes(
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id, updated_at);
        """)
        db().commit()

    # ---------- helpers ----------
    now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    def error(status, message, **extra):
        return jsonify({"error": message, **extra}), status

    def make_token(user_id):
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_HOURS)
        return jwt.encode({"sub": str(user_id), "exp": exp}, app.config["SECRET"], algorithm="HS256")

    def login_required(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return error(401, "Missing bearer token")
            try:
                payload = jwt.decode(header[7:], app.config["SECRET"], algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return error(401, "Token expired")
            except jwt.InvalidTokenError:
                return error(401, "Invalid token")
            g.user_id = int(payload["sub"])
            return fn(*a, **kw)
        return wrapper

    def note_json(row):
        return {k: row[k] for k in ("id", "title", "body", "created_at", "updated_at")}

    def read_note_input(partial=False):
        data = request.get_json(silent=True) or {}
        problems = {}
        title, body = data.get("title"), data.get("body")
        if title is None and not partial:
            problems["title"] = "required"
        if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 120):
            problems["title"] = "must be 1 to 120 characters"
        if body is not None and (not isinstance(body, str) or len(body) > 10000):
            problems["body"] = "must be text up to 10,000 characters"
        return data, problems

    # ---------- auth ----------
    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        email, password = str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
        problems = {}
        if "@" not in email or "." not in email.split("@")[-1]: problems["email"] = "must be a valid email"
        if len(password) < 8: problems["password"] = "must be at least 8 characters"
        if problems: return error(422, "Validation failed", fields=problems)
        try:
            cur = db().execute("INSERT INTO users(email, password_hash, created_at) VALUES(?,?,?)",
                               (email, generate_password_hash(password), now()))
            db().commit()
        except sqlite3.IntegrityError:
            return error(409, "Email already registered")
        return jsonify({"token": make_token(cur.lastrowid), "user": {"id": cur.lastrowid, "email": email}}), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        row = db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], str(data.get("password", ""))):
            return error(401, "Wrong email or password")       # same message either way
        return jsonify({"token": make_token(row["id"]), "user": {"id": row["id"], "email": row["email"]}})

    @app.get("/api/me")
    @login_required
    def me():
        row = db().execute("SELECT id, email, created_at FROM users WHERE id = ?", (g.user_id,)).fetchone()
        return jsonify(dict(row)) if row else error(401, "Invalid token")

    # ---------- notes CRUD ----------
    @app.get("/api/notes")
    @login_required
    def list_notes():
        try:
            page = max(int(request.args.get("page", 1)), 1)
            limit = min(max(int(request.args.get("limit", 20)), 1), 100)
        except ValueError:
            return error(422, "page and limit must be numbers")
        q = f"%{request.args.get('q', '').strip()}%"
        where = "user_id = ? AND (title LIKE ? OR body LIKE ?)"
        total = db().execute(f"SELECT COUNT(*) FROM notes WHERE {where}", (g.user_id, q, q)).fetchone()[0]
        rows = db().execute(f"SELECT * FROM notes WHERE {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                            (g.user_id, q, q, limit, (page - 1) * limit)).fetchall()
        return jsonify({"items": [note_json(r) for r in rows], "page": page, "limit": limit, "total": total})

    @app.post("/api/notes")
    @login_required
    def create_note():
        data, problems = read_note_input()
        if problems: return error(422, "Validation failed", fields=problems)
        t = now()
        cur = db().execute("INSERT INTO notes(user_id, title, body, created_at, updated_at) VALUES(?,?,?,?,?)",
                           (g.user_id, data["title"].strip(), data.get("body", ""), t, t))
        db().commit()
        row = db().execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(note_json(row)), 201

    def own_note(note_id):   # a user can only ever see their own notes
        return db().execute("SELECT * FROM notes WHERE id = ? AND user_id = ?", (note_id, g.user_id)).fetchone()

    @app.get("/api/notes/<int:note_id>")
    @login_required
    def get_note(note_id):
        row = own_note(note_id)
        return jsonify(note_json(row)) if row else error(404, "Note not found")

    @app.put("/api/notes/<int:note_id>")
    @app.patch("/api/notes/<int:note_id>")
    @login_required
    def update_note(note_id):
        row = own_note(note_id)
        if not row: return error(404, "Note not found")
        data, problems = read_note_input(partial=True)
        if problems: return error(422, "Validation failed", fields=problems)
        title = data["title"].strip() if "title" in data else row["title"]
        body = data.get("body", row["body"])
        db().execute("UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ?", (title, body, now(), note_id))
        db().commit()
        return jsonify(note_json(own_note(note_id)))

    @app.delete("/api/notes/<int:note_id>")
    @login_required
    def delete_note(note_id):
        if not own_note(note_id): return error(404, "Note not found")
        db().execute("DELETE FROM notes WHERE id = ?", (note_id,))
        db().commit()
        return "", 204

    @app.errorhandler(404)
    def not_found(_): return error(404, "Not found")

    @app.errorhandler(405)
    def bad_method(_): return error(405, "Method not allowed")

    return app


if __name__ == "__main__":
    create_app().run(port=5000)
