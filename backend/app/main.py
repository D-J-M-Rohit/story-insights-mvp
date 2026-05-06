from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import create_access_token, get_current_user, hash_password, password_too_long, verify_password
from .config import settings
from .llm_gateway import LLMGateway
from .pdf_report import build_report_pdf
from .report_interpreter import generate_interpretation
from .scoring import score_session
from .schemas import (
    NextSceneRequest,
    ReportOut,
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
    list_sessions_for_user,
    list_choices,
    list_scenes,
    save_choice,
    save_report,
    save_scene,
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
    session = create_session(current_user["id"], payload.scenario, payload.max_turns)
    return {
        "id": session["id"],
        "user_id": session["user_id"],
        "scenario": session["scenario"],
        "max_turns": session["max_turns"],
        "status": session["status"],
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
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in rows
    ]


@app.post("/api/v1/scenes/next", response_model=SceneOut)
def next_scene(payload: NextSceneRequest, current_user=Depends(get_current_user)):
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
    scene = gateway.generate_scene(session, history, turn)
    save_scene(scene)
    return {
        "id": scene["id"],
        "turn": scene["turn"],
        "title": scene["title"],
        "scene": scene["scene"],
        "time_limit_sec": scene["time_limit_sec"],
        "options": scene["options"],
        "scene_metadata": scene.get("scene_metadata"),
    }


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
