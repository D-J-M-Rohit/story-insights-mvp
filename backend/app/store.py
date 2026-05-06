import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from .database import SessionLocal, init_db as _init_db
from .models import Choice, Report, Scene, Session, User


def _now():
    return datetime.now(timezone.utc)


def _to_dict(model):
    if model is None:
        return None
    out = {}
    for key, value in model.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, datetime):
            out[key] = value.isoformat()
            continue
        out[key] = value
    return out


def init_db():
    _init_db()


def create_user(email, password_hash, role="participant"):
    with SessionLocal() as db:
        user = User(email=email, password_hash=password_hash, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return _to_dict(user)


def get_user_by_email(email):
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        return _to_dict(user)


def get_user_by_id(user_id):
    with SessionLocal() as db:
        user = db.get(User, user_id)
        return _to_dict(user)


def create_session(user_id, scenario, max_turns):
    with SessionLocal() as db:
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            scenario=scenario,
            max_turns=max_turns,
            current_turn=0,
            status="active",
            created_at=_now(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return _to_dict(session)


def get_session(session_id):
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        return _to_dict(session)


def list_sessions_for_user(user_id):
    with SessionLocal() as db:
        rows = db.execute(
            select(Session).where(Session.user_id == user_id).order_by(Session.created_at.desc())
        ).scalars()
        return [_to_dict(row) for row in rows]


def assert_session_owner(session_id, user_id):
    session = get_session(session_id)
    if not session:
        return None
    return session if session["user_id"] == user_id else None


def update_session_turn(session_id, turn):
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        if not session:
            return None
        session.current_turn = turn
        db.commit()
        db.refresh(session)
        return _to_dict(session)


def complete_session(session_id):
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        if not session:
            return None
        session.status = "complete"
        session.completed_at = _now()
        db.commit()
        db.refresh(session)
        return _to_dict(session)


def save_scene(scene):
    with SessionLocal() as db:
        row = Scene(
            id=scene["id"],
            session_id=scene["session_id"],
            turn=scene["turn"],
            title=scene["title"],
            scene=scene["scene"],
            options_json=scene["options"],
            scene_metadata=scene.get("scene_metadata") or {},
            time_limit_sec=scene.get("time_limit_sec", 45),
            created_at=_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        out = _to_dict(row)
        out["options"] = out.pop("options_json", [])
        return out


def get_scene(scene_id):
    with SessionLocal() as db:
        row = db.get(Scene, scene_id)
        if not row:
            return None
        out = _to_dict(row)
        out["options"] = out.pop("options_json", [])
        return out


def list_scenes(session_id):
    with SessionLocal() as db:
        rows = db.execute(select(Scene).where(Scene.session_id == session_id).order_by(Scene.turn.asc())).scalars()
        result = []
        for row in rows:
            out = _to_dict(row)
            out["options"] = out.pop("options_json", [])
            result.append(out)
        return result


def save_choice(
    session_id,
    scene_id,
    turn,
    option_id,
    option_text,
    traits,
    telemetry,
    time_limit_sec,
    options,
    scene_metadata,
):
    with SessionLocal() as db:
        row = Choice(
            id=str(uuid.uuid4()),
            session_id=session_id,
            scene_id=scene_id,
            turn=turn,
            option_id=option_id,
            option_text=option_text,
            traits_json=traits or {},
            telemetry_json=telemetry or {},
            options_json=options or [],
            scene_metadata=scene_metadata or {},
            time_limit_sec=int(time_limit_sec or 45),
            created_at=_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def list_choices(session_id):
    with SessionLocal() as db:
        rows = db.execute(select(Choice).where(Choice.session_id == session_id).order_by(Choice.turn.asc())).scalars()
        result = []
        for row in rows:
            item = _to_dict(row)
            item["traits"] = item.pop("traits_json", {}) or {}
            item["telemetry"] = item.pop("telemetry_json", {}) or {}
            item["options"] = item.pop("options_json", []) or []
            item["scene_metadata"] = item.get("scene_metadata", {}) or {}
            item["time_limit_sec"] = int(item.get("time_limit_sec") or 45)
            result.append(item)
        return result


def save_report(session_id, report):
    with SessionLocal() as db:
        existing = db.get(Report, session_id)
        if existing:
            existing.report_json = report
            existing.updated_at = _now()
        else:
            db.add(Report(session_id=session_id, report_json=report, created_at=_now(), updated_at=_now()))
        db.commit()


def get_report(session_id):
    with SessionLocal() as db:
        row = db.get(Report, session_id)
        return row.report_json if row else None
