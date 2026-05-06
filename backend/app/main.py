from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import create_access_token, get_current_user, hash_password, password_too_long, verify_password
from .config import settings
from .llm_gateway import LLMGateway
from .pdf_report import build_report_pdf
from .policy_trace import build_output_hash, build_policy_trace
from .prompt_policy import POLICY_VERSION, build_policy_input, decide_policy
from .prompts import build_scene_prompt
from .report_interpreter import generate_interpretation
from .scenario_packs import get_default_pack_for_scenario, seed_builtin_packs, validate_pack
from .scoring import score_session
from .scene_validation import validate_scene_against_policy
from .schemas import (
    NextSceneRequest,
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
from .store import (
    assert_session_owner,
    complete_session,
    create_session,
    create_user,
    get_report,
    get_scene,
    get_session,
    get_user_by_email,
    init_db,
    get_policy_trace,
    get_scenario_pack,
    list_policy_traces,
    list_scenario_packs,
    list_sessions_for_user,
    list_choices,
    list_scenes,
    save_choice,
    save_policy_trace,
    save_report,
    save_scene,
    update_policy_trace_scene,
    update_session_turn,
)

app = FastAPI(title="Story Insights MVP")
gateway = LLMGateway()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    seed_builtin_packs()


@app.get("/health")
def health():
    return {"ok": True}


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
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "role": user["role"]}}


@app.get("/api/v1/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@app.post("/api/v1/sessions", response_model=SessionOut)
def create_session_endpoint(payload: SessionCreate, current_user=Depends(get_current_user)):
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
        save_choice(
            session_id=session["id"],
            scene_id=payload.scene_id,
            turn=prev_scene["turn"],
            option_id=payload.choice_id,
            option_text=selected_option["text"] if selected_option else "No selection",
            traits=selected_option["traits"] if selected_option else {},
            telemetry=(payload.telemetry.model_dump() if payload.telemetry else {}),
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
    prompt_preview = build_scene_prompt(session["scenario"], turn, session["max_turns"], history, policy=policy, pack=pack)
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
    scene = gateway.generate_scene(session, history, turn, policy=policy, pack=pack)
    validation = scene.get("_meta", {}).get("validation") or validate_scene_against_policy(scene, policy, pack)
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


@app.get("/api/v1/reports/{session_id}", response_model=ReportOut)
def report(session_id: str, current_user=Depends(get_current_user)):
    session = assert_session_owner(session_id, current_user["id"])
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found_or_forbidden")
    existing = get_report(session_id)
    if existing and existing.get("interpretation"):
        return existing
    if existing:
        report_data = existing
    else:
        choices = list_choices(session_id)
        report_data = score_session(session, choices)
    report_data["scenario"] = report_data.get("scenario") or session.get("scenario")
    report_data["interpretation"] = report_data.get("interpretation") or generate_interpretation(
        report_data, report_data.get("scenario", "general")
    )
    save_report(session_id, report_data)
    return report_data


@app.get("/api/v1/reports/{session_id}/pdf")
def report_pdf(session_id: str, current_user=Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail="pdf_generation_failed") from exc

    headers = {"Content-Disposition": f'attachment; filename="story-insights-report-{session_id}.pdf"'}
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
