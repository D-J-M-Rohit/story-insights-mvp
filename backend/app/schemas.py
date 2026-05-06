from typing import List, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    scenario: str = "workplace"
    max_turns: int = 20


class SessionOut(BaseModel):
    id: str
    user_id: str
    scenario: str
    max_turns: int
    status: str
    created_at: Optional[str] = None


class HoverEvent(BaseModel):
    option_id: str
    t_ms: int


class Telemetry(BaseModel):
    latency_ms: int = 0
    hover_log: List[HoverEvent] = Field(default_factory=list)
    hover_switch_count: int = 0
    changed_intent: bool = False
    timed_out: bool = False


class SceneOption(BaseModel):
    id: str
    text: str
    traits: dict
    construct_tags: List[str] = Field(default_factory=list)
    quality: Optional[float] = None
    quality_dimensions: Optional[dict] = None


class SceneOut(BaseModel):
    id: str
    turn: int
    title: str
    scene: str
    time_limit_sec: int = 45
    options: List[SceneOption]
    scene_metadata: Optional[dict] = None


class NextSceneRequest(BaseModel):
    session_id: str
    scene_id: Optional[str] = None
    choice_id: Optional[str] = None
    telemetry: Optional[Telemetry] = None


class UserRegister(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FeatureOut(BaseModel):
    name: str
    key: str
    score: float
    description: str
    raw_score: Optional[float] = None
    evidence_count: int = 0
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None
    interpretation_status: Optional[str] = None


class PenOut(BaseModel):
    name: str
    score: float
    key: Optional[str] = None


class ReportOut(BaseModel):
    session_id: str
    scenario: Optional[str] = None
    summary: str
    features: List[FeatureOut]
    pen: List[PenOut]
    choices: List[dict]
    interpretation: Optional[dict] = None
