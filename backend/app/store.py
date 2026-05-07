import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .database import SessionLocal, init_db as _init_db
from .models import (
    Choice,
    ContextTrace,
    DerivedFeature,
    FeedbackDailyMetric,
    FeedbackEvent,
    GenerationTrace,
    PolicyTrace,
    PromptTemplate,
    Report,
    ScenarioPack,
    Scene,
    Session,
    User,
)


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


def _coerce_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return _now()
    return value


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
        payload = dict(trace)
        if "created_at" in payload:
            payload["created_at"] = _coerce_datetime(payload["created_at"])
        row = PolicyTrace(**payload)
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


def save_context_trace(trace: dict):
    with SessionLocal() as db:
        payload = dict(trace)
        if "created_at" in payload:
            payload["created_at"] = _coerce_datetime(payload["created_at"])
        row = ContextTrace(**payload)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def update_context_trace(
    trace_id: str,
    scene_id: str | None = None,
    prompt_hash: str | None = None,
    output_hash: str | None = None,
    latency_ms: int | None = None,
):
    with SessionLocal() as db:
        row = db.get(ContextTrace, trace_id)
        if not row:
            return None
        if scene_id is not None:
            row.scene_id = scene_id
        if prompt_hash is not None:
            row.prompt_hash = prompt_hash
        if output_hash is not None:
            row.output_hash = output_hash
        if latency_ms is not None:
            row.latency_ms = latency_ms
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def list_context_traces(session_id: str):
    with SessionLocal() as db:
        rows = db.execute(
            select(ContextTrace).where(ContextTrace.session_id == session_id).order_by(ContextTrace.turn.asc())
        ).scalars()
        return [_to_dict(row) for row in rows]


def get_context_trace(session_id: str, turn: int):
    with SessionLocal() as db:
        row = db.execute(
            select(ContextTrace).where(ContextTrace.session_id == session_id, ContextTrace.turn == turn)
        ).scalar_one_or_none()
        return _to_dict(row)


def save_generation_trace(trace: dict):
    with SessionLocal() as db:
        payload = dict(trace)
        if "created_at" in payload:
            payload["created_at"] = _coerce_datetime(payload["created_at"])
        row = GenerationTrace(**payload)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def update_generation_trace(
    trace_id_or_id: str,
    scene_id: str | None = None,
    status: str | None = None,
    duration_ms: int | None = None,
    response_hash: str | None = None,
    token_usage_input: int | None = None,
    token_usage_output: int | None = None,
    fallback_reason: str | None = None,
    error_type: str | None = None,
    trace_json_patch: dict | None = None,
):
    with SessionLocal() as db:
        row = db.get(GenerationTrace, trace_id_or_id)
        if not row:
            row = db.execute(select(GenerationTrace).where(GenerationTrace.trace_id == trace_id_or_id)).scalar_one_or_none()
        if not row:
            return None
        if scene_id is not None:
            row.scene_id = scene_id
        if status is not None:
            row.status = status
        if duration_ms is not None:
            row.duration_ms = duration_ms
        if response_hash is not None:
            row.response_hash = response_hash
        if token_usage_input is not None:
            row.token_usage_input = token_usage_input
        if token_usage_output is not None:
            row.token_usage_output = token_usage_output
        if fallback_reason is not None:
            row.fallback_reason = fallback_reason
        if error_type is not None:
            row.error_type = error_type
        if trace_json_patch:
            merged = dict(row.trace_json or {})
            merged.update(trace_json_patch)
            row.trace_json = merged
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def list_generation_traces(session_id: str):
    with SessionLocal() as db:
        rows = db.execute(
            select(GenerationTrace).where(GenerationTrace.session_id == session_id).order_by(GenerationTrace.turn.asc())
        ).scalars()
        return [_to_dict(r) for r in rows]


def get_generation_trace_for_scene(scene_id: str):
    with SessionLocal() as db:
        row = db.execute(select(GenerationTrace).where(GenerationTrace.scene_id == scene_id)).scalar_one_or_none()
        return _to_dict(row)


def save_derived_feature(feature: dict):
    with SessionLocal() as db:
        row = DerivedFeature(**feature)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def save_derived_features(session_id: str, features: list[dict]):
    saved = []
    for f in features or []:
        payload = dict(f)
        payload["session_id"] = session_id
        saved.append(save_derived_feature(payload))
    return saved


def list_derived_features(session_id: str):
    with SessionLocal() as db:
        rows = db.execute(select(DerivedFeature).where(DerivedFeature.session_id == session_id)).scalars()
        return [_to_dict(r) for r in rows]


def delete_derived_features(session_id: str) -> None:
    with SessionLocal() as db:
        rows = db.execute(select(DerivedFeature).where(DerivedFeature.session_id == session_id)).scalars().all()
        for r in rows:
            db.delete(r)
        db.commit()


def create_feedback_event(event: dict) -> dict:
    with SessionLocal() as db:
        row = FeedbackEvent(**event)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def get_feedback_event(feedback_id: str):
    with SessionLocal() as db:
        row = db.get(FeedbackEvent, feedback_id)
        return _to_dict(row)


def list_feedback_for_user(user_id: str, session_id: str | None = None):
    with SessionLocal() as db:
        query = select(FeedbackEvent).where(FeedbackEvent.user_id == user_id)
        if session_id:
            query = query.where(FeedbackEvent.session_id == session_id)
        rows = db.execute(query.order_by(FeedbackEvent.created_at.desc())).scalars()
        return [_to_dict(r) for r in rows]


def list_feedback_for_session(session_id: str):
    with SessionLocal() as db:
        rows = db.execute(
            select(FeedbackEvent).where(FeedbackEvent.session_id == session_id).order_by(FeedbackEvent.created_at.desc())
        ).scalars()
        return [_to_dict(r) for r in rows]


def list_feedback_for_admin(status: str | None = None, limit: int = 50, offset: int = 0):
    with SessionLocal() as db:
        query = select(FeedbackEvent)
        if status:
            query = query.where(FeedbackEvent.moderation_status == status)
        rows = db.execute(query.order_by(FeedbackEvent.created_at.desc()).offset(offset).limit(limit)).scalars()
        return [_to_dict(r) for r in rows]


def review_feedback_event(feedback_id: str, moderation_status: str, reviewer_note: str | None = None):
    with SessionLocal() as db:
        row = db.get(FeedbackEvent, feedback_id)
        if not row:
            return None
        row.moderation_status = moderation_status
        row.reviewer_note = reviewer_note
        row.reviewed_at = _now()
        if moderation_status == "deleted":
            row.comment = None
            row.comment_redacted = None
        elif moderation_status == "redacted":
            row.comment = None
        db.commit()
        db.refresh(row)
        return _to_dict(row)


def purge_old_feedback_comments(retention_days: int = 90) -> int:
    cutoff = _now() - timedelta(days=int(retention_days or 90))
    purged = 0
    with SessionLocal() as db:
        rows = db.execute(
            select(FeedbackEvent).where(FeedbackEvent.created_at < cutoff, FeedbackEvent.comment.is_not(None))
        ).scalars().all()
        for row in rows:
            row.comment = None
            row.comment_redacted = None
            purged += 1
        db.commit()
    return purged


def rollup_feedback_daily_metrics(retention_days: int = 365) -> dict:
    with SessionLocal() as db:
        events = db.execute(select(FeedbackEvent)).scalars().all()
        grouped = {}
        for e in events:
            day = (e.created_at.date().isoformat() if e.created_at else "")
            scenario = (e.evidence_ref_json or {}).get("scenario")
            scenario_pack_id = (e.evidence_ref_json or {}).get("scenario_pack_id")
            key = (day, scenario, scenario_pack_id, e.channel, e.feedback_type)
            grouped.setdefault(key, []).append(e)
        upserts = 0
        for (day, scenario, scenario_pack_id, channel, feedback_type), rows in grouped.items():
            useful = [r.rating_useful for r in rows if r.rating_useful is not None]
            engaging = [r.rating_engaging for r in rows if r.rating_engaging is not None]
            tag_counter = Counter()
            for r in rows:
                tag_counter.update(r.tags_json or [])
            existing = db.execute(
                select(FeedbackDailyMetric).where(
                    FeedbackDailyMetric.day == day,
                    FeedbackDailyMetric.scenario == scenario,
                    FeedbackDailyMetric.scenario_pack_id == scenario_pack_id,
                    FeedbackDailyMetric.channel == channel,
                    FeedbackDailyMetric.feedback_type == feedback_type,
                )
            ).scalar_one_or_none()
            payload = {
                "day": day,
                "scenario": scenario,
                "scenario_pack_id": scenario_pack_id,
                "channel": channel,
                "feedback_type": feedback_type,
                "submitted_count": len(rows),
                "flagged_count": sum(1 for r in rows if r.moderation_status == "flagged"),
                "dismissed_count": sum(1 for r in rows if r.moderation_status == "deleted"),
                "avg_useful": (sum(useful) / len(useful)) if useful else None,
                "avg_engaging": (sum(engaging) / len(engaging)) if engaging else None,
                "tags_json": dict(tag_counter),
                "updated_at": _now(),
            }
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
            else:
                db.add(FeedbackDailyMetric(id=str(uuid.uuid4()), created_at=_now(), **payload))
            upserts += 1
        cutoff = (_now() - timedelta(days=int(retention_days or 365))).date().isoformat()
        old = db.execute(select(FeedbackDailyMetric).where(FeedbackDailyMetric.day < cutoff)).scalars().all()
        deleted = len(old)
        for row in old:
            db.delete(row)
        db.commit()
    return {"upserted": upserts, "deleted_old": deleted}


def get_feedback_profile(session_id: str) -> dict:
    from .feedback import build_feedback_profile

    events = list_feedback_for_session(session_id)
    current_turn = max([int(e.get("turn") or 0) for e in events] + [0])
    return build_feedback_profile(events, current_turn=current_turn)
