import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .config import settings


def _now():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn, table, columns):
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for col, col_type in columns:
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")


def init_db():
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY,
          scenario TEXT,
          max_turns INTEGER,
          current_turn INTEGER,
          status TEXT,
          created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scenes (
          id TEXT PRIMARY KEY,
          session_id TEXT,
          turn INTEGER,
          title TEXT,
          scene TEXT,
          options_json TEXT,
          time_limit_sec INTEGER,
          scene_metadata_json TEXT,
          created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS choices (
          id TEXT PRIMARY KEY,
          session_id TEXT,
          scene_id TEXT,
          turn INTEGER,
          option_id TEXT,
          option_text TEXT,
          traits_json TEXT,
          telemetry_json TEXT,
          options_json TEXT,
          scene_metadata_json TEXT,
          time_limit_sec INTEGER,
          created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
          session_id TEXT PRIMARY KEY,
          report_json TEXT,
          created_at TEXT
        )
        """
    )
    _ensure_columns(conn, "scenes", [("scene_metadata_json", "TEXT")])
    _ensure_columns(
        conn,
        "choices",
        [
            ("options_json", "TEXT"),
            ("scene_metadata_json", "TEXT"),
            ("time_limit_sec", "INTEGER"),
        ],
    )
    conn.commit()
    conn.close()


def create_session(scenario, max_turns):
    session_id = str(uuid.uuid4())
    data = {
        "id": session_id,
        "scenario": scenario,
        "max_turns": max_turns,
        "current_turn": 0,
        "status": "active",
        "created_at": _now(),
    }
    conn = _conn()
    conn.execute(
        """
        INSERT INTO sessions (id, scenario, max_turns, current_turn, status, created_at)
        VALUES (:id, :scenario, :max_turns, :current_turn, :status, :created_at)
        """,
        data,
    )
    conn.commit()
    conn.close()
    return data


def get_session(session_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_session_turn(session_id, turn):
    conn = _conn()
    conn.execute("UPDATE sessions SET current_turn = ? WHERE id = ?", (turn, session_id))
    conn.commit()
    conn.close()


def complete_session(session_id):
    conn = _conn()
    conn.execute("UPDATE sessions SET status = 'complete' WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def save_scene(scene):
    conn = _conn()
    conn.execute(
        """
        INSERT INTO scenes (id, session_id, turn, title, scene, options_json, time_limit_sec, scene_metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scene["id"],
            scene["session_id"],
            scene["turn"],
            scene["title"],
            scene["scene"],
            json.dumps(scene["options"]),
            scene["time_limit_sec"],
            json.dumps(scene.get("scene_metadata") or {}),
            _now(),
        ),
    )
    conn.commit()
    conn.close()


def get_scene(scene_id):
    conn = _conn()
    row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    conn.close()
    if not row:
        return None
    out = dict(row)
    out["options"] = json.loads(out["options_json"])
    meta = out.get("scene_metadata_json")
    out["scene_metadata"] = json.loads(meta) if meta else {}
    return out


def list_scenes(session_id):
    conn = _conn()
    rows = conn.execute("SELECT * FROM scenes WHERE session_id = ? ORDER BY turn ASC", (session_id,)).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["options"] = json.loads(item["options_json"])
        meta = item.get("scene_metadata_json")
        item["scene_metadata"] = json.loads(meta) if meta else {}
        result.append(item)
    return result


def save_choice(
    session_id,
    scene_id,
    turn,
    option_id,
    option_text,
    traits,
    telemetry,
    options=None,
    scene_metadata=None,
    time_limit_sec=45,
):
    conn = _conn()
    conn.execute(
        """
        INSERT INTO choices (id, session_id, scene_id, turn, option_id, option_text, traits_json, telemetry_json, options_json, scene_metadata_json, time_limit_sec, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            session_id,
            scene_id,
            turn,
            option_id,
            option_text,
            json.dumps(traits or {}),
            json.dumps(telemetry or {}),
            json.dumps(options or []),
            json.dumps(scene_metadata or {}),
            int(time_limit_sec or 45),
            _now(),
        ),
    )
    conn.commit()
    conn.close()


def list_choices(session_id):
    conn = _conn()
    rows = conn.execute("SELECT * FROM choices WHERE session_id = ? ORDER BY turn ASC", (session_id,)).fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["traits"] = json.loads(item["traits_json"] or "{}")
        item["telemetry"] = json.loads(item["telemetry_json"] or "{}")
        raw_opts = item.get("options_json")
        item["options"] = json.loads(raw_opts) if raw_opts else []
        meta = item.get("scene_metadata_json")
        item["scene_metadata"] = json.loads(meta) if meta else {}
        tl = item.get("time_limit_sec")
        item["time_limit_sec"] = int(tl) if tl is not None else 45
        for key in ("traits_json", "telemetry_json", "options_json", "scene_metadata_json"):
            item.pop(key, None)
        result.append(item)
    return result


def save_report(session_id, report):
    conn = _conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO reports (session_id, report_json, created_at)
        VALUES (?, ?, ?)
        """,
        (session_id, json.dumps(report), _now()),
    )
    conn.commit()
    conn.close()


def get_report(session_id):
    conn = _conn()
    row = conn.execute("SELECT report_json FROM reports WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["report_json"])
