from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .llm_gateway import LLMGateway
from .scoring import score_session
from .schemas import NextSceneRequest, ReportOut, SceneOut, SessionCreate, SessionOut
from .store import (
    complete_session,
    create_session,
    get_report,
    get_scene,
    get_session,
    init_db,
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


@app.post("/api/v1/sessions", response_model=SessionOut)
def create_session_endpoint(payload: SessionCreate):
    session = create_session(payload.scenario, payload.max_turns)
    return {
        "id": session["id"],
        "scenario": session["scenario"],
        "max_turns": session["max_turns"],
        "status": session["status"],
    }


@app.post("/api/v1/scenes/next", response_model=SceneOut)
def next_scene(payload: NextSceneRequest):
    session = get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    if session["status"] != "active":
        raise HTTPException(status_code=410, detail="assessment_complete")

    if payload.scene_id:
        prev_scene = get_scene(payload.scene_id)
        if not prev_scene:
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
            options=prev_scene.get("options") or [],
            scene_metadata=prev_scene.get("scene_metadata") or {},
            time_limit_sec=prev_scene.get("time_limit_sec", 45),
        )
        update_session_turn(session["id"], prev_scene["turn"])
        session = get_session(session["id"])

    if session["current_turn"] >= session["max_turns"]:
        complete_session(session["id"])
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
def report(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    existing = get_report(session_id)
    if existing:
        return existing
    choices = list_choices(session_id)
    report_data = score_session(session, choices)
    save_report(session_id, report_data)
    return report_data
