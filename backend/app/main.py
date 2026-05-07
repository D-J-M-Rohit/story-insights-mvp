from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import create_access_token, get_current_user, hash_password, password_too_long, verify_password
from .config import settings
from .context_builder import build_context_bundle
from .evidence_mapper import attach_evidence_to_report, build_derived_features
from .generation_trace import build_generation_trace_start, finalize_generation_trace
from .llm_gateway import LLMGateway
from .logging_config import configure_logging, hash_identifier, log_event
from .metrics import metrics_response, record_auth_failure, record_report_generation, record_request
from .pdf_report import build_report_pdf
from .policy_trace import build_output_hash, build_policy_trace
from .prompt_policy import POLICY_VERSION, build_policy_input, decide_policy
from .prompts import build_scene_prompt
from .rate_limit import RateLimitMiddleware
from .request_context import clear_request_context, get_request_context, set_request_context
from .report_interpreter import generate_interpretation
from .scenario_packs import get_default_pack_for_scenario, seed_builtin_packs, validate_pack
from .scoring import score_session
from .scene_validation import validate_scene_against_policy
from .telemetry import normalize_telemetry
from .schemas import (
    ConfidenceOut,
    ContextPreviewRequest,
    DerivedFeatureOut,
    GenerationTraceOut,
    NextSceneRequest,
    MetricsSummaryOut,
    ProviderStatusOut,
    PolicyDecisionOut,
    PolicyPreviewRequest,
    ReportOut,
    ScenarioPackOut,
    SceneOut,
    SessionCreate,
    SessionOut,
    TokenOut,
    UserLogin,
    UserOut,
    UserRegister,
)
from .provider_health import provider_health_tracker
from .store import (
    delete_derived_features,
    get_generation_trace_for_scene,
    list_generation_traces,
    list_derived_features,
    save_derived_features,
    save_generation_trace,
    update_generation_trace,
    assert_session_owner,
    complete_session,
    create_session,
    create_user,
    get_report,
    get_scene,
    get_session,
    get_user_by_email,
    init_db,
    get_context_trace,
    get_policy_trace,
    get_scenario_pack,
    list_context_traces,
    list_policy_traces,
    list_scenario_packs,
    list_sessions_for_user,
    list_choices,
    list_scenes,
    save_choice,
    save_context_trace,
    save_policy_trace,
    save_report,
    save_scene,
    update_context_trace,
    update_policy_trace_scene,
    update_session_turn,
)

app = FastAPI(title="Story Insights MVP")
gateway = LLMGateway()
configure_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def request_observability_middleware(request, call_next):
    started = perf_counter()
    ctx = get_request_context(request)
    set_request_context(request_id=ctx["request_id"], trace_id=ctx["trace_id"])
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        status_code = response.status_code if response is not None else 500
        traceparent = f"00-{ctx['trace_id']}-{'0'*16}-{ctx.get('trace_flags','01')}"
        if response is not None:
            response.headers["X-Request-ID"] = ctx["request_id"]
            response.headers["traceparent"] = traceparent
        record_request(request.method, request.url.path, status_code, duration_ms / 1000.0)
        log_event(
            "request_completed",
            route=request.url.path,
            method=request.method,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        clear_request_context()


@app.on_event("startup")
def startup():
    init_db()
    seed_builtin_packs()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return metrics_response()


@app.get("/api/v1/provider/status", response_model=ProviderStatusOut)
def provider_status(current_user=Depends(get_current_user)):
    set_request_context(user_hash=hash_identifier(current_user.get("id")))
    return provider_health_tracker.snapshot()


@app.get("/api/v1/provider/metrics-summary", response_model=MetricsSummaryOut)
def provider_metrics_summary(current_user=Depends(get_current_user)):
    set_request_context(user_hash=hash_identifier(current_user.get("id")))
    snap = provider_health_tracker.snapshot()
    return {
        "provider": snap,
        "request_counts": {
            "ok": snap.get("counts", {}).get("ok", 0),
            "fallback": snap.get("counts", {}).get("fallback", 0),
            "error": snap.get("counts", {}).get("error", 0),
        },
        "fallback_counts": snap.get("recent_fallback_reasons", {}),
        "latency_summary": snap.get("latency_ms", {}),
    }


@app.post("/api/v1/auth/register", response_model=TokenOut)
def register(payload: UserRegister):
    if len(payload.password or "") < 8:
        raise HTTPException(status_code=400, detail="password_too_short")
    if password_too_long(payload.password):
        raise HTTPException(status_code=400, detail="password_too_long")
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=400, detail="email_already_exists")
    try:
        pw_hash = hash_password(payload.password)
    except ValueError:
        raise HTTPException(status_code=400, detail="password_too_long")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="password_hash_failed") from exc
    user = create_user(payload.email.strip().lower(), pw_hash)
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


@app.post("/api/v1/auth/login", response_model=TokenOut)
def login(payload: UserLogin):
    user = get_user_by_email(payload.email.strip().lower())
    if not user or not verify_password(payload.password, user["password_hash"]):
        record_auth_failure("invalid_credentials")
        raise HTTPException(status_code=401, detail="invalid_credentials")
    set_request_context(user_hash=hash_identifier(user["id"]))
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


@app.get("/api/v1/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    set_request_context(user_hash=hash_identifier(current_user.get("id")))
    return current_user


@app.post("/api/v1/sessions", response_model=SessionOut)
def create_session_endpoint(payload: SessionCreate, current_user=Depends(get_current_user)):
    set_request_context(user_hash=hash_identifier(current_user.get("id")))
    pack = get_scenario_pack(payload.scenario_pack_id) if payload.scenario_pack_id else None
    if not pack:
        pack = get_default_pack_for_scenario(payload.scenario)
    session = create_session(
        current_user["id"],
        payload.scenario,
        payload.max_turns,
        scenario_pack_id=pack.get("id"),
        policy_version=POLICY_VERSION,
    )
    return {
        "id": session["id"],
        "user_id": session["user_id"],
        "scenario": session["scenario"],
        "max_turns": session["max_turns"],
        "status": session["status"],
        "scenario_pack_id": session.get("scenario_pack_id"),
        "policy_version": session.get("policy_version"),
        "created_at": str(session["created_at"]),
    }


@app.get("/api/v1/my-sessions")
def my_sessions(current_user=Depends(get_current_user)):
    rows = list_sessions_for_user(current_user["id"])
    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "scenario": row["scenario"],
            "max_turns": row["max_turns"],
            "current_turn": row["current_turn"],
            "status": row["status"],
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]


@app.post("/api/v1/scenes/next", response_model=SceneOut)
def next_scene(payload: NextSceneRequest, current_user=Depends(get_current_user)):
    started = perf_counter()
    session = assert_session_owner(payload.session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    if session["status"] != "active":
        raise HTTPException(status_code=410, detail="assessment_complete")

    if payload.scene_id:
        prev_scene = get_scene(payload.scene_id)
        if not prev_scene or prev_scene["session_id"] != session["id"]:
            raise HTTPException(status_code=404, detail="scene_not_found")
        selected_option = None
        for option in prev_scene["options"]:
            if option["id"] == payload.choice_id:
                selected_option = option
                break
        normalized_telemetry = normalize_telemetry(
            (payload.telemetry.model_dump() if payload.telemetry else {}),
            prev_scene.get("time_limit_sec", 45),
        )
        save_choice(
            session_id=session["id"],
            scene_id=payload.scene_id,
            turn=prev_scene["turn"],
            option_id=payload.choice_id,
            option_text=selected_option["text"] if selected_option else "No selection",
            traits=selected_option["traits"] if selected_option else {},
            telemetry=normalized_telemetry,
            time_limit_sec=prev_scene.get("time_limit_sec", 45),
            options=prev_scene.get("options") or [],
            scene_metadata=prev_scene.get("scene_metadata") or {},
        )
        update_session_turn(session["id"], prev_scene["turn"])
        session = get_session(session["id"])

    if session["current_turn"] >= session["max_turns"]:
        complete_session(session["id"])
        existing = get_report(session["id"])
        if not existing:
            choices = list_choices(session["id"])
            report_data = score_session(session, choices)
            report_data["scenario"] = session.get("scenario")
            report_data["interpretation"] = generate_interpretation(report_data, session.get("scenario", "general"))
            save_report(session["id"], report_data)
        raise HTTPException(status_code=410, detail="assessment_complete")

    turn = session["current_turn"] + 1
    scenes = list_scenes(session["id"])
    choices = list_choices(session["id"])
    pack = get_scenario_pack(session.get("scenario_pack_id")) if session.get("scenario_pack_id") else None
    if pack and pack.get("pack_json"):
        pack = pack["pack_json"]
    if not pack:
        pack = get_default_pack_for_scenario(session["scenario"])

    policy = decide_policy(session, choices, pack, turn)
    policy_input = build_policy_input(session, choices, pack, turn)
    history = []
    for sc in scenes:
        chosen = next((c for c in choices if c["scene_id"] == sc["id"]), None)
        history.append(
            {
                "turn": sc["turn"],
                "title": sc["title"],
                "selected_option": chosen["option_id"] if chosen else None,
            }
        )
    context_bundle, context_trace = build_context_bundle(
        session=session,
        scenes=scenes,
        choices=choices,
        policy={**policy, "turn": turn},
        pack=pack,
        policy_trace_id=None,
    )
    prompt_preview = build_scene_prompt(
        session["scenario"],
        turn,
        session["max_turns"],
        history,
        policy=policy,
        pack=pack,
        context_bundle=context_bundle,
    )
    trace = build_policy_trace(
        session_id=session["id"],
        turn=turn,
        scenario_pack_id=policy["scenario_pack_id"],
        prompt_version=policy["prompt_version"],
        policy_version=policy["policy_version"],
        provider=(settings.LLM_PROVIDER or "mock").lower(),
        model_snapshot=gateway.model_snapshot((settings.LLM_PROVIDER or "mock").lower()),
        policy_input=policy_input,
        policy_output=policy,
        prompt_text=prompt_preview,
    )
    trace_row = save_policy_trace(trace)
    context_bundle, context_trace = build_context_bundle(
        session=session,
        scenes=scenes,
        choices=choices,
        policy={**policy, "turn": turn},
        pack=pack,
        policy_trace_id=trace_row.get("id"),
    )
    saved_context_trace = save_context_trace(context_trace)
    gen_trace = build_generation_trace_start(
        session=session,
        turn=turn,
        provider=(settings.LLM_PROVIDER or "mock").lower(),
        model=gateway.model_snapshot((settings.LLM_PROVIDER or "mock").lower()),
        prompt=prompt_preview,
        policy=policy,
        context_bundle=context_bundle,
        policy_trace=trace_row,
        context_trace=saved_context_trace,
    )
    saved_gen_trace = save_generation_trace(gen_trace)
    gen_started = perf_counter()
    scene = gateway.generate_scene(session, history, turn, policy=policy, pack=pack, context_bundle=context_bundle)
    validation = scene.get("_meta", {}).get("validation") or validate_scene_against_policy(
        scene, policy, pack, context_bundle=context_bundle
    )
    fallback_reason = scene.get("_meta", {}).get("fallback_reason")
    latency_ms = scene.get("_meta", {}).get("latency_ms", int((perf_counter() - started) * 1000))
    scene.pop("_meta", None)
    save_scene(scene)
    update_policy_trace_scene(
        trace_row["id"],
        scene["id"],
        build_output_hash(scene),
        validation,
        latency_ms,
        fallback_reason,
    )
    update_context_trace(
        trace_id=saved_context_trace["id"],
        scene_id=scene["id"],
        prompt_hash=trace_row.get("prompt_hash"),
        output_hash=build_output_hash(scene),
        latency_ms=context_trace.get("latency_ms"),
    )
    provider_name = (settings.LLM_PROVIDER or "mock").lower()
    final_status = "ok" if provider_name == "mock" else ("fallback" if fallback_reason else "ok")
    finalized_gen = finalize_generation_trace(
        saved_gen_trace,
        scene=scene,
        status=final_status,
        started_at_monotonic=gen_started,
        provider_response_metadata={},
        fallback_reason=(None if provider_name == "mock" else fallback_reason),
        validation=validation,
    )
    update_generation_trace(
        finalized_gen["id"],
        scene_id=finalized_gen.get("scene_id"),
        status=finalized_gen.get("status"),
        duration_ms=finalized_gen.get("duration_ms"),
        response_hash=finalized_gen.get("response_hash"),
        token_usage_input=finalized_gen.get("token_usage_input"),
        token_usage_output=finalized_gen.get("token_usage_output"),
        fallback_reason=finalized_gen.get("fallback_reason"),
        error_type=finalized_gen.get("error_type"),
        trace_json_patch=finalized_gen.get("trace_json"),
    )
    return {
        "id": scene["id"],
        "turn": scene["turn"],
        "title": scene["title"],
        "scene": scene["scene"],
        "time_limit_sec": scene["time_limit_sec"],
        "options": scene["options"],
        "scene_metadata": scene.get("scene_metadata"),
        "scenario_pack_id": (scene.get("scene_metadata") or {}).get("scenario_pack_id"),
        "prompt_version": (scene.get("scene_metadata") or {}).get("prompt_version"),
        "policy_version": (scene.get("scene_metadata") or {}).get("policy_version"),
    }


@app.get("/api/v1/scenario-packs", response_model=list[ScenarioPackOut])
def scenario_packs(current_user=Depends(get_current_user)):
    rows = list_scenario_packs()
    out = []
    for row in rows:
        pack = row.get("pack_json", {})
        if row.get("status") != "active":
            continue
        out.append(
            {
                "id": row["id"],
                "slug": row["slug"],
                "version": row["version"],
                "scenario": row["scenario"],
                "title": pack.get("title", row["slug"]),
                "description": pack.get("description", ""),
                "max_turns_default": pack.get("max_turns_default", 5),
            }
        )
    return out


@app.get("/api/v1/scenario-packs/{pack_id}")
def scenario_pack_detail(pack_id: str, current_user=Depends(get_current_user)):
    row = get_scenario_pack(pack_id)
    if not row:
        raise HTTPException(status_code=404, detail="pack_not_found")
    return row.get("pack_json", {})


@app.post("/api/v1/scenario-packs/{pack_id}/validate")
def scenario_pack_validate(pack_id: str, current_user=Depends(get_current_user)):
    row = get_scenario_pack(pack_id)
    if not row:
        raise HTTPException(status_code=404, detail="pack_not_found")
    pack = row.get("pack_json", {})
    valid, errors = validate_pack(pack)
    return {"valid": valid, "errors": errors, "warnings": []}


@app.post("/api/v1/policy/preview", response_model=PolicyDecisionOut)
def policy_preview(payload: PolicyPreviewRequest, current_user=Depends(get_current_user)):
    if payload.session_id:
        session = assert_session_owner(payload.session_id, current_user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
        scenario = session["scenario"]
        choices = payload.choices if payload.choices is not None else list_choices(session["id"])
    else:
        scenario = payload.scenario or "workplace"
        session = {"id": f"preview:{current_user['id']}", "scenario": scenario, "max_turns": 5}
        choices = payload.choices or []
    pack = get_default_pack_for_scenario(scenario)
    return decide_policy(session, choices, pack, payload.turn)


@app.get("/api/v1/policy-traces/{session_id}")
def policy_traces(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    return list_policy_traces(session_id)


@app.get("/api/v1/policy-traces/{session_id}/{turn}")
def policy_trace_for_turn(session_id: str, turn: int, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    trace = get_policy_trace(session_id, turn)
    if not trace:
        raise HTTPException(status_code=404, detail="policy_trace_not_found")
    return trace


@app.get("/api/v1/context-traces/{session_id}")
def context_traces(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    return list_context_traces(session_id)


@app.get("/api/v1/context-traces/{session_id}/{turn}")
def context_trace_for_turn(session_id: str, turn: int, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    trace = get_context_trace(session_id, turn)
    if not trace:
        raise HTTPException(status_code=404, detail="context_trace_not_found")
    return trace


@app.post("/api/v1/context/preview")
def context_preview(payload: ContextPreviewRequest, current_user=Depends(get_current_user)):
    if payload.session_id:
        session = assert_session_owner(payload.session_id, current_user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
        scenes = list_scenes(session["id"])
        choices = list_choices(session["id"])
        scenario = session["scenario"]
    else:
        scenario = payload.scenario or "workplace"
        session = {"id": f"context-preview:{current_user['id']}", "scenario": scenario, "max_turns": 5}
        scenes = []
        choices = []
    pack_row = get_scenario_pack(payload.scenario_pack_id) if payload.scenario_pack_id else None
    pack = pack_row["pack_json"] if pack_row and pack_row.get("pack_json") else get_default_pack_for_scenario(scenario)
    policy = payload.policy or decide_policy(session, choices, pack, payload.turn)
    bundle, trace = build_context_bundle(
        session=session,
        scenes=scenes,
        choices=choices,
        policy={**policy, "turn": payload.turn},
        pack=pack,
        policy_trace_id=None,
    )
    return {"context_bundle": bundle, "retrieval_scores": trace.get("retrieval_scores_json", {})}


@app.get("/api/v1/reports/{session_id}", response_model=ReportOut)
def report(session_id: str, current_user=Depends(get_current_user)):
    started = perf_counter()
    set_request_context(user_hash=hash_identifier(current_user.get("id")), session_id=session_id)
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    existing = get_report(session_id)
    if existing:
        report_data = existing
    else:
        choices = list_choices(session_id)
        report_data = score_session(session, choices)
    choices = list_choices(session_id)
    report_data = attach_evidence_to_report(report_data, choices, session=session)
    delete_derived_features(session_id)
    derived = save_derived_features(session_id, build_derived_features(session, report_data, choices))
    report_data["derived_features"] = derived
    report_data["scenario"] = report_data.get("scenario") or session.get("scenario")
    report_data["interpretation"] = report_data.get("interpretation") or generate_interpretation(
        report_data, report_data.get("scenario", "general")
    )
    save_report(session_id, report_data)
    record_report_generation("ok", perf_counter() - started)
    return report_data


@app.get("/api/v1/reports/{session_id}/pdf")
def report_pdf(session_id: str, current_user=Depends(get_current_user)):
    started = perf_counter()
    set_request_context(user_hash=hash_identifier(current_user.get("id")), session_id=session_id)
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    report_data = get_report(session_id)
    if not report_data:
        choices = list_choices(session_id)
        report_data = score_session(session, choices)
        report_data["scenario"] = session.get("scenario")
        report_data["interpretation"] = generate_interpretation(report_data, session.get("scenario", "general"))
        save_report(session_id, report_data)
    try:
        pdf_buffer = build_report_pdf(report_data)
    except Exception as exc:
        record_report_generation("error", perf_counter() - started)
        raise HTTPException(status_code=500, detail="pdf_generation_failed") from exc

    headers = {"Content-Disposition": f'attachment; filename="story-insights-report-{session_id}.pdf"'}
    record_report_generation("ok", perf_counter() - started)
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)


@app.get("/api/v1/reports/{session_id}/evidence")
def report_evidence(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    report_data = get_report(session_id)
    if not report_data:
        choices = list_choices(session_id)
        report_data = score_session(session, choices)
    if "evidence_cards" not in report_data:
        report_data = attach_evidence_to_report(report_data, list_choices(session_id), session=session)
        save_report(session_id, report_data)
    return {"session_id": session_id, "evidence_cards": report_data.get("evidence_cards", [])}


@app.get("/api/v1/reports/{session_id}/derived-features")
def report_derived_features(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    return {"session_id": session_id, "derived_features": list_derived_features(session_id)}


@app.get("/api/v1/reports/{session_id}/confidence")
def report_confidence(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    derived = list_derived_features(session_id)
    if not derived:
        report_data = get_report(session_id) or score_session(session, list_choices(session_id))
        report_data = attach_evidence_to_report(report_data, list_choices(session_id), session=session)
        derived = save_derived_features(session_id, build_derived_features(session, report_data, list_choices(session_id)))
    levels = [d.get("confidence_level", "exploratory") for d in derived]
    overall = "directional" if "directional" in levels else ("exploratory" if "exploratory" in levels else "insufficient_evidence")
    features = [
        {
            "key": d.get("feature_key"),
            "score": d.get("feature_score"),
            "low": d.get("confidence_low"),
            "high": d.get("confidence_high"),
            "level": d.get("confidence_level"),
            "evidence_count": d.get("evidence_count"),
        }
        for d in derived
    ]
    return {
        "session_id": session_id,
        "confidence_summary": {
            "overall_level": overall,
            "completed_turns": len(list_choices(session_id)),
            "expected_turns": int(session.get("max_turns") or 0),
            "message": "Scores are directional estimates from a short interactive session.",
        },
        "features": features,
    }


@app.get("/api/v1/debug/sessions/{session_id}/traces", response_model=list[GenerationTraceOut])
def debug_session_traces(session_id: str, kind: str = "generation", current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    if kind != "generation":
        return []
    rows = list_generation_traces(session_id)
    for row in rows:
        row.pop("trace_json", None)
    return rows


@app.get("/api/v1/debug/scenes/{scene_id}/generation-trace", response_model=GenerationTraceOut)
def debug_scene_trace(scene_id: str, current_user=Depends(get_current_user)):
    scene = get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="scene_not_found")
    session = assert_session_owner(scene["session_id"], current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    row = get_generation_trace_for_scene(scene_id)
    if not row:
        raise HTTPException(status_code=404, detail="generation_trace_not_found")
    row.pop("trace_json", None)
    return row
