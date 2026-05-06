import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from .database import SessionLocal, init_db as _init_db
from .models import Choice, PolicyTrace, PromptTemplate, Report, ScenarioPack, Scene, Session, User


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


def create_session(user_id, scenario, max_turns, scenario_pack_id=None, policy_version=None):
    with SessionLocal() as db:
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            scenario=scenario,
            max_turns=max_turns,
            current_turn=0,
            status="active",
            scenario_pack_id=scenario_pack_id,
            policy_version=policy_version,
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


def upsert_scenario_pack(pack: dict) -> dict:
    with SessionLocal() as db:
        existing = db.get(ScenarioPack, pack["id"])
        if existing:
            existing.slug = pack["slug"]
            existing.version = pack["version"]
            existing.scenario = pack["scenario"]
            existing.status = pack.get("status", "active")
            existing.pack_json = pack
            existing.updated_at = _now()
            row = existing
        else:
            row = ScenarioPack(
                id=pack["id"],
                slug=pack["slug"],
                version=pack["version"],
                scenario=pack["scenario"],
                status=pack.get("status", "active"),
                pack_json=pack,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def get_scenario_pack(pack_id: str):
    with SessionLocal() as db:
        row = db.get(ScenarioPack, pack_id)
        return _to_dict(row)


def get_active_scenario_pack_for_scenario(scenario: str):
    with SessionLocal() as db:
        row = db.execute(
            select(ScenarioPack)
            .where(ScenarioPack.scenario == scenario, ScenarioPack.status == "active")
            .order_by(ScenarioPack.updated_at.desc())
        ).scalar_one_or_none()
        return _to_dict(row)


def list_scenario_packs():
    with SessionLocal() as db:
        rows = db.execute(select(ScenarioPack).order_by(ScenarioPack.scenario.asc(), ScenarioPack.slug.asc())).scalars()
        return [_to_dict(row) for row in rows]


def save_policy_trace(trace: dict):
    with SessionLocal() as db:
        row = PolicyTrace(**trace)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def update_policy_trace_scene(
    trace_id: str,
    scene_id: str,
    output_hash: str | None,
    validation: dict,
    latency_ms: int | None,
    fallback_reason: str | None,
):
    with SessionLocal() as db:
        row = db.get(PolicyTrace, trace_id)
        if not row:
            return None
        row.scene_id = scene_id
        row.output_hash = output_hash
        row.validation_json = validation or {}
        row.latency_ms = latency_ms
        row.fallback_reason = fallback_reason
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def list_policy_traces(session_id: str):
    with SessionLocal() as db:
        rows = db.execute(
            select(PolicyTrace).where(PolicyTrace.session_id == session_id).order_by(PolicyTrace.turn.asc())
        ).scalars()
        return [_to_dict(row) for row in rows]


def get_policy_trace(session_id: str, turn: int):
    with SessionLocal() as db:
        row = db.execute(
            select(PolicyTrace).where(PolicyTrace.session_id == session_id, PolicyTrace.turn == turn)
        ).scalar_one_or_none()
        return _to_dict(row)
