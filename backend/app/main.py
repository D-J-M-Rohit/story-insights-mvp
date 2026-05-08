from time import perf_counter

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import create_access_token, get_current_user, hash_password, password_too_long, verify_password
from .config import settings
from .context_builder import build_context_bundle
from .embeddings import seed_embeddings
from .evidence_mapper import attach_evidence_to_report, build_derived_features
from .feedback import build_feedback_event, normalize_feedback_payload, sanitize_feedback_event
from .generation_trace import build_generation_trace_start, finalize_generation_trace
from .archive_service import archive_faiss_snapshot, archive_generation_trace, archive_pdf_bytes, archive_prompt_payload, purge_expired_archives
from .benchmark_baselines import attach_benchmark_comparisons
from .circuit_breaker import get_provider_circuit_breaker
from .llm_gateway import LLMGateway
from .logging_config import configure_logging, hash_identifier, log_event
from .metrics import (
    metrics_response,
    record_auth_failure,
    record_feedback_event,
    record_feedback_flagged,
    record_feedback_opt_in,
    record_feedback_review_latency,
    record_report_generation,
    record_request,
    set_feedback_admin_queue_size,
)
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
from .security_headers import apply_security_headers
from .telemetry import normalize_telemetry
from .retrieval import build_faiss_index, get_active_faiss_index, retrieve_context
from .object_store import get_signed_download_url
from .schemas import (
    AuthOut,
    ConfidenceOut,
    ContextPreviewRequest,
    FeedbackCreate,
    FeedbackOut,
    FeedbackReview,
    FeedbackSummaryOut,
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
    SceneOption,
    SessionCreate,
    SessionDetailOut,
    SessionOut,
    SessionStateOut,
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
    get_feedback_event,
    get_feedback_profile,
    list_context_traces,
    list_feedback_for_admin,
    list_feedback_for_session,
    list_feedback_for_user,
    list_policy_traces,
    list_scenario_packs,
    list_sessions_for_user,
    list_choices,
    list_scenes,
    save_choice,
    create_feedback_event,
    feedback_idempotency_get,
    feedback_idempotency_set,
    get_existing_micro_feedback,
    get_resume_scene_for_session,
    save_context_trace,
    save_policy_trace,
    save_report,
    save_scene,
    update_context_trace,
    update_policy_trace_scene,
    update_session_turn,
    purge_old_feedback_comments,
    review_feedback_event,
    rollup_feedback_daily_metrics,
    create_archived_blob,
    create_faiss_index_metadata,
    get_archived_blob,
    list_fragment_embeddings_for_index,
    list_archived_blobs_for_report,
    mark_archived_blob_deleted,
    set_active_faiss_index,
)

app = FastAPI(title="Story Insights MVP")
gateway = LLMGateway()
configure_logging()
circuit_breaker = get_provider_circuit_breaker(settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    apply_security_headers(response, settings)
    return response


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
        "circuit_breaker": circuit_breaker.get_all_snapshots(),
    }


@app.get("/api/v1/provider/circuit-status")
def provider_circuit_status(current_user=Depends(get_current_user)):
    _require_admin(current_user)
    return {"enabled": bool(settings.PROVIDER_CIRCUIT_BREAKER_ENABLED), "circuits": circuit_breaker.get_all_snapshots()}


def _require_admin(current_user):
    if (current_user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin_required")


def _set_auth_cookie(response: Response, token: str):
    if not settings.AUTH_COOKIE_ENABLED:
        return
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=bool(settings.AUTH_COOKIE_SECURE),
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=int(settings.AUTH_COOKIE_MAX_AGE_MINUTES) * 60,
        path="/",
    )


def _clear_auth_cookie(response: Response):
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        secure=bool(settings.AUTH_COOKIE_SECURE),
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def _include_bearer_token_in_body(request: Request) -> bool:
    if not settings.AUTH_COOKIE_ENABLED:
        return True
    if settings.AUTH_RETURN_TOKEN_IN_BODY:
        return True
    if settings.AUTH_ALLOW_TOKEN_RESPONSE_OVERRIDE:
        if (request.headers.get("X-Return-Bearer-Token") or "").lower() in ("true", "1", "yes"):
            return True
        if (request.query_params.get("include_token") or "").lower() in ("true", "1", "yes"):
            return True
    return False


def _auth_response(user_row: dict, token: str, request: Request) -> dict:
    user_out = {"id": user_row["id"], "email": user_row["email"], "role": user_row["role"]}
    if _include_bearer_token_in_body(request):
        return {"access_token": token, "token_type": "bearer", "user": user_out}
    return {"token_type": "cookie", "user": user_out}


def _session_detail_out(session: dict) -> SessionDetailOut:
    return SessionDetailOut(
        id=session["id"],
        user_id=session["user_id"],
        scenario=session["scenario"],
        max_turns=session["max_turns"],
        current_turn=int(session.get("current_turn") or 0),
        status=session["status"],
        created_at=str(session["created_at"]) if session.get("created_at") else None,
        completed_at=str(session["completed_at"]) if session.get("completed_at") else None,
        duration_ms=session.get("duration_ms"),
        scenario_pack_id=session.get("scenario_pack_id"),
        policy_version=session.get("policy_version"),
    )


def _scene_row_to_scene_out(scene: dict) -> SceneOut:
    opts: list[SceneOption] = []
    for o in scene.get("options") or []:
        opts.append(
            SceneOption(
                id=o["id"],
                text=o["text"],
                traits=o.get("traits") or {},
                construct_tags=o.get("construct_tags") or [],
                quality=o.get("quality"),
                quality_dimensions=o.get("quality_dimensions"),
            )
        )
    meta = scene.get("scene_metadata") or {}
    return SceneOut(
        id=scene["id"],
        turn=scene["turn"],
        title=scene["title"],
        scene=scene["scene"],
        time_limit_sec=scene.get("time_limit_sec", 45),
        options=opts,
        scene_metadata=scene.get("scene_metadata"),
        scenario_pack_id=meta.get("scenario_pack_id"),
        prompt_version=meta.get("prompt_version"),
        policy_version=meta.get("policy_version"),
    )


@app.post("/api/v1/auth/register", response_model=AuthOut)
def register(payload: UserRegister, response: Response, request: Request):
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
    _set_auth_cookie(response, token)
    lean = {k: v for k, v in user.items() if k != "password_hash"}
    return _auth_response(lean, token, request)


@app.post("/api/v1/auth/login", response_model=AuthOut)
def login(payload: UserLogin, response: Response, request: Request):
    user = get_user_by_email(payload.email.strip().lower())
    if not user or not verify_password(payload.password, user["password_hash"]):
        record_auth_failure("invalid_credentials")
        raise HTTPException(status_code=401, detail="invalid_credentials")
    set_request_context(user_hash=hash_identifier(user["id"]))
    token = create_access_token(user)
    _set_auth_cookie(response, token)
    lean = {k: v for k, v in user.items() if k != "password_hash"}
    return _auth_response(lean, token, request)


@app.post("/api/v1/auth/logout")
def logout(response: Response):
    _clear_auth_cookie(response)
    return {"ok": True}


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


@app.get("/api/v1/sessions/{session_id}", response_model=SessionDetailOut)
def session_detail(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    return _session_detail_out(session)


@app.get("/api/v1/sessions/{session_id}/state", response_model=SessionStateOut)
def session_state(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    choices = list_choices(session_id)
    resume_scene = get_resume_scene_for_session(session_id)
    latest = _scene_row_to_scene_out(resume_scene) if resume_scene else None
    completed = session.get("status") != "active"
    report_ready = completed and bool(get_report(session_id))
    return SessionStateOut(
        session=_session_detail_out(session),
        latest_scene=latest,
        choices_count=len(choices),
        can_resume=session.get("status") == "active",
        report_ready=report_ready,
    )


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
    else:
        # Idempotency guard for first-scene fetches (for example React Strict Mode
        # or transient client retries). If an unanswered scene already exists,
        # return it instead of generating a new scene.
        resume_scene = get_resume_scene_for_session(session["id"])
        if resume_scene:
            return _scene_row_to_scene_out(resume_scene)

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
    feedback_profile = get_feedback_profile(session["id"])
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
        feedback_profile=feedback_profile,
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
        feedback_profile=feedback_profile,
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
    if settings.OBJECT_ARCHIVE_ENABLED:
        archive_generation_trace(finalized_gen)
        archive_prompt_payload(
            {
                "session_id": session["id"],
                "generation_trace_id": finalized_gen.get("id"),
                "prompt_hash": trace_row.get("prompt_hash"),
                "policy_version": policy.get("policy_version"),
                "prompt_version": policy.get("prompt_version"),
            }
        )
    debug_payload = None
    if settings.BENCHMARK_DEBUG_FIELDS_ENABLED:
        q = (context_trace or {}).get("query_json") or {}
        debug_payload = {
            "retrieval_ms": q.get("retrieval_ms"),
            "retrieval_backend": q.get("retrieval_backend", settings.RETRIEVAL_BACKEND),
            "retrieved_count": q.get("retrieval_count", 0),
            "retrieval_fallback_used": bool(q.get("retrieval_fallback_used")),
            "retrieval_fallback_reason": q.get("retrieval_fallback_reason") or "",
            "fallback_used": bool(fallback_reason),
        }
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
        **({"debug": debug_payload} if debug_payload is not None else {}),
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
        feedback_profile=(get_feedback_profile(session["id"]) if payload.session_id else None),
    )
    return {"context_bundle": bundle, "retrieval_scores": trace.get("retrieval_scores_json", {})}


@app.post("/api/v1/feedback")
def submit_feedback(
    payload: FeedbackCreate,
    current_user=Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    if not settings.FEEDBACK_ENABLED:
        raise HTTPException(status_code=404, detail="feedback_disabled")
    session = assert_session_owner(payload.session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    if payload.report_id and payload.report_id != payload.session_id:
        raise HTTPException(status_code=400, detail="invalid_report_reference")
    idem = (idempotency_key or "").strip()
    if idem:
        existing_fid = feedback_idempotency_get(current_user["id"], idem)
        if existing_fid:
            existing_ev = get_feedback_event(existing_fid)
            if existing_ev:
                return {
                    "id": existing_ev.get("id"),
                    "status": "duplicate_ignored",
                    "existing_id": existing_ev.get("id"),
                    "moderation_status": existing_ev.get("moderation_status"),
                    "raw_retention_until": sanitize_feedback_event(existing_ev).get("raw_retention_until"),
                }
    report_data = get_report(payload.session_id) if payload.report_id else None
    scene = get_scene(payload.scene_id) if payload.scene_id else None
    try:
        normalized = normalize_feedback_payload(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if normalized["feedback_type"] == "micro":
        existing_micro = get_existing_micro_feedback(
            current_user["id"], normalized["session_id"], normalized.get("turn")
        )
        if existing_micro:
            return {
                "id": existing_micro.get("id"),
                "status": "duplicate_ignored",
                "existing_id": existing_micro.get("id"),
                "moderation_status": existing_micro.get("moderation_status"),
                "raw_retention_until": sanitize_feedback_event(existing_micro).get("raw_retention_until"),
            }
    event = build_feedback_event(normalized, current_user=current_user, session=session, scene=scene, report=report_data)
    saved = create_feedback_event(event)
    if idem:
        feedback_idempotency_set(current_user["id"], idem, saved.get("id"))
    record_feedback_event(
        channel=saved.get("channel"),
        feedback_type=saved.get("feedback_type"),
        category=saved.get("category") or "unknown",
        status=saved.get("moderation_status"),
    )
    if saved.get("consent_comment"):
        record_feedback_opt_in(saved.get("channel"))
    for reason in saved.get("moderation_flags_json") or []:
        record_feedback_flagged(reason)
    if saved.get("moderation_status") == "flagged":
        log_event(
            "feedback_flagged",
            feedback_id=saved.get("id"),
            session_id=saved.get("session_id"),
            moderation_flags=saved.get("moderation_flags_json") or [],
        )
    log_event(
        "feedback_submitted",
        feedback_id=saved.get("id"),
        session_id=saved.get("session_id"),
        channel=saved.get("channel"),
        feedback_type=saved.get("feedback_type"),
        moderation_status=saved.get("moderation_status"),
        moderation_flags=saved.get("moderation_flags_json") or [],
    )
    return {
        "id": saved.get("id"),
        "status": "accepted",
        "moderation_status": saved.get("moderation_status"),
        "raw_retention_until": sanitize_feedback_event(saved).get("raw_retention_until"),
    }


@app.get("/api/v1/feedback/my", response_model=list[FeedbackOut])
def my_feedback(session_id: str | None = None, current_user=Depends(get_current_user)):
    if session_id:
        session = assert_session_owner(session_id, current_user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    rows = list_feedback_for_user(current_user["id"], session_id=session_id)
    return [sanitize_feedback_event(r, include_comment=True) for r in rows]


@app.get("/api/v1/feedback/summary", response_model=FeedbackSummaryOut)
def feedback_summary(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    rows = list_feedback_for_session(session_id)
    useful = [r.get("rating_useful") for r in rows if r.get("rating_useful") is not None]
    engaging = [r.get("rating_engaging") for r in rows if r.get("rating_engaging") is not None]
    tags = {}
    topic_counts = {}
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for row in rows:
        for tag in row.get("tags_json") or []:
            tags[tag] = tags.get(tag, 0) + 1
        analysis = row.get("analysis_json") or {}
        for topic in analysis.get("topics") or []:
            key = topic.get("key")
            label = topic.get("label") or key
            if not key:
                continue
            if key not in topic_counts:
                topic_counts[key] = {"key": key, "label": label, "count": 0}
            topic_counts[key]["count"] += 1
        sentiment = (analysis.get("sentiment") or {}).get("label")
        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1
    created_values = [r.get("created_at") for r in rows if r.get("created_at") is not None]
    latest = max(created_values) if created_values else None
    top_topics = sorted(topic_counts.values(), key=lambda item: item.get("count", 0), reverse=True)[:5]
    return {
        "session_id": session_id,
        "submitted_count": len(rows),
        "avg_useful": (sum(useful) / len(useful)) if useful else None,
        "avg_engaging": (sum(engaging) / len(engaging)) if engaging else None,
        "tags": tags,
        "flagged_count": sum(1 for r in rows if r.get("moderation_status") == "flagged"),
        "top_topics": top_topics,
        "sentiment_counts": sentiment_counts,
        "latest_created_at": latest,
    }


@app.get("/api/v1/admin/feedback", response_model=list[FeedbackOut])
def admin_feedback_list(status: str = "flagged", limit: int = 50, offset: int = 0, current_user=Depends(get_current_user)):
    _require_admin(current_user)
    rows = list_feedback_for_admin(status=status, limit=limit, offset=offset)
    set_feedback_admin_queue_size(len(rows))
    return [sanitize_feedback_event(r, include_comment=True) for r in rows]


@app.patch("/api/v1/admin/feedback/{feedback_id}", response_model=FeedbackOut)
def admin_feedback_review(feedback_id: str, payload: FeedbackReview, current_user=Depends(get_current_user)):
    _require_admin(current_user)
    if payload.moderation_status not in {"clean", "flagged", "redacted", "deleted", "resolved"}:
        raise HTTPException(status_code=400, detail="invalid_moderation_status")
    before = get_feedback_event(feedback_id)
    row = review_feedback_event(feedback_id, payload.moderation_status, payload.reviewer_note)
    if not row:
        raise HTTPException(status_code=404, detail="feedback_not_found")
    if before and before.get("created_at") and row.get("reviewed_at"):
        try:
            from datetime import datetime

            created_dt = datetime.fromisoformat(str(before["created_at"]).replace("Z", "+00:00"))
            reviewed_dt = datetime.fromisoformat(str(row["reviewed_at"]).replace("Z", "+00:00"))
            record_feedback_review_latency((reviewed_dt - created_dt).total_seconds())
        except Exception:
            pass
    log_event(
        "feedback_reviewed",
        feedback_id=row.get("id"),
        session_id=row.get("session_id"),
        moderation_status=row.get("moderation_status"),
    )
    return sanitize_feedback_event(row, include_comment=True)


@app.post("/api/v1/admin/feedback/rollup")
def admin_feedback_rollup(current_user=Depends(get_current_user)):
    _require_admin(current_user)
    result = rollup_feedback_daily_metrics(settings.FEEDBACK_AGGREGATE_RETENTION_DAYS)
    return result


@app.post("/api/v1/admin/feedback/purge-old")
def admin_feedback_purge_old(current_user=Depends(get_current_user)):
    _require_admin(current_user)
    purged = purge_old_feedback_comments(settings.FEEDBACK_RAW_RETENTION_DAYS)
    log_event("feedback_purged", purged_count=purged)
    return {"purged_count": purged}


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
    if settings.BENCHMARK_COMPARISONS_ENABLED:
        report_data = attach_benchmark_comparisons(report_data)
    delete_derived_features(session_id)
    derived = save_derived_features(session_id, build_derived_features(session, report_data, choices))
    report_data["derived_features"] = derived
    report_data["scenario"] = report_data.get("scenario") or session.get("scenario")
    report_data["started_at"] = session.get("created_at")
    report_data["completed_at"] = session.get("completed_at")
    report_data["duration_ms"] = session.get("duration_ms")
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
    if settings.BENCHMARK_COMPARISONS_ENABLED:
        report_data = attach_benchmark_comparisons(report_data)
    report_data["started_at"] = session.get("created_at")
    report_data["completed_at"] = session.get("completed_at")
    report_data["duration_ms"] = session.get("duration_ms")
    try:
        pdf_buffer = build_report_pdf(report_data)
    except Exception as exc:
        record_report_generation("error", perf_counter() - started)
        raise HTTPException(status_code=500, detail="pdf_generation_failed") from exc

    if settings.OBJECT_ARCHIVE_ENABLED and settings.ARCHIVE_PDFS_ENABLED:
        try:
            archive_pdf_bytes(session_id=session_id, report_id=session_id, pdf_bytes=pdf_buffer.getvalue(), report_version="latest")
        except Exception:
            pass

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


@app.post("/api/v1/admin/embeddings/seed")
def admin_seed_embeddings(payload: dict, current_user=Depends(get_current_user)):
    _require_admin(current_user)
    scenario_pack_id = payload.get("scenario_pack_id")
    force = bool(payload.get("force", False))
    return seed_embeddings(scenario_pack_id=scenario_pack_id, force=force)


@app.post("/api/v1/admin/faiss/rebuild")
def admin_rebuild_faiss(payload: dict, current_user=Depends(get_current_user)):
    _require_admin(current_user)
    index_name = payload.get("index_name") or settings.FAISS_INDEX_NAME
    scenario_pack_id = payload.get("scenario_pack_id")
    meta = build_faiss_index(
        index_name=index_name,
        filters={"scenario_pack_id": scenario_pack_id, "active": True} if scenario_pack_id else {"active": True},
    )
    if settings.OBJECT_ARCHIVE_ENABLED and isinstance(meta, dict) and meta.get("local_path"):
        archive_faiss_snapshot(meta["local_path"], meta)
    return meta


@app.get("/api/v1/admin/faiss/status")
def admin_faiss_status(current_user=Depends(get_current_user)):
    _require_admin(current_user)
    meta = get_active_faiss_index(settings.FAISS_INDEX_NAME)
    if not meta:
        return {"status": "no_active_index", "index_name": settings.FAISS_INDEX_NAME}
    return {"status": "ok", "active_index": meta}


@app.post("/api/v1/retrieval/search")
def retrieval_search(payload: dict, current_user=Depends(get_current_user)):
    query_text = str(payload.get("query_text") or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query_text_required")
    filters = payload.get("filters") or {}
    k = int(payload.get("k") or settings.RETRIEVAL_TOP_K)
    return {"results": retrieve_context(query_text=query_text, filters=filters, k=k)}


@app.post("/api/v1/admin/archive/run")
def admin_archive_run(payload: dict, current_user=Depends(get_current_user)):
    _require_admin(current_user)
    result = {"purged": None}
    if payload.get("purge_expired", True):
        result["purged"] = purge_expired_archives(limit=200)
    return result


@app.get("/api/v1/admin/archive/blob/{blob_id}/signed-url")
def admin_archive_blob_signed_url(blob_id: str, current_user=Depends(get_current_user)):
    _require_admin(current_user)
    blob = get_archived_blob(blob_id)
    if not blob:
        raise HTTPException(status_code=404, detail="blob_not_found")
    return {"blob_id": blob_id, "signed_url": get_signed_download_url(blob.get("object_key"))}


@app.get("/api/v1/reports/{session_id}/pdf-url")
def report_pdf_url(session_id: str, current_user=Depends(get_current_user)):
    if not settings.ARCHIVE_PDFS_ENABLED:
        raise HTTPException(status_code=404, detail="pdf_archive_disabled")
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    blobs = list_archived_blobs_for_report(session_id, blob_type="pdf")
    if not blobs:
        raise HTTPException(status_code=404, detail="archived_pdf_not_found")
    blob = blobs[0]
    return {"report_id": session_id, "signed_url": get_signed_download_url(blob.get("object_key"))}
