from typing import List, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    scenario: str = "workplace"
    max_turns: int = 20
    scenario_pack_id: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    user_id: str
    scenario: str
    max_turns: int
    status: str
    scenario_pack_id: Optional[str] = None
    policy_version: Optional[str] = None
    created_at: Optional[str] = None


class HoverEvent(BaseModel):
    option_id: str
    t_ms: int


class Telemetry(BaseModel):
    latency_ms: int = 0
    hover_log: List[HoverEvent] = Field(default_factory=list)
    hover_dwell_ms_by_option: Optional[dict] = None
    hover_switch_count: int = 0
    first_hovered_option_id: Optional[str] = None
    last_hovered_option_id: Optional[str] = None
    option_view_order: Optional[List[str]] = None
    focus_lost_count: Optional[int] = 0
    browser_focus_lost: Optional[bool] = False
    latency_ratio: Optional[float] = None
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
    scenario_pack_id: Optional[str] = None
    prompt_version: Optional[str] = None
    policy_version: Optional[str] = None


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
    evidence_cards: Optional[List[dict]] = None


class EvidenceCardOut(BaseModel):
    feature_key: str
    feature_name: str
    score: float
    bucket: str
    label: str
    evidence: List[str]
    components: dict
    source_choice_ids: List[str] = Field(default_factory=list)
    disclaimer: str


class GenerationTraceOut(BaseModel):
    id: str
    session_id: str
    scene_id: Optional[str] = None
    turn: int
    trace_id: str
    provider: Optional[str] = None
    request_model: Optional[str] = None
    status: str
    duration_ms: Optional[int] = None
    prompt_hash: Optional[str] = None
    context_hash: Optional[str] = None
    policy_hash: Optional[str] = None
    response_hash: Optional[str] = None
    fallback_reason: Optional[str] = None
    created_at: Optional[str] = None


class PolicyDecisionOut(BaseModel):
    target_construct: str
    difficulty: float
    ambiguity: float
    time_pressure: float
    conflict_affordance: float
    prompt_template: str
    prompt_version: str
    scenario_pack_id: str
    policy_version: str
    time_limit_sec: int
    rationale: Optional[dict] = None


class ScenarioPackOut(BaseModel):
    id: str
    slug: str
    version: str
    scenario: str
    title: str
    description: str
    max_turns_default: int


class PolicyPreviewRequest(BaseModel):
    scenario: Optional[str] = None
    session_id: Optional[str] = None
    turn: int
    choices: Optional[List[dict]] = None


class ContextPreviewRequest(BaseModel):
    session_id: Optional[str] = None
    scenario: Optional[str] = None
    scenario_pack_id: Optional[str] = None
    turn: int = 1
    policy: Optional[dict] = None
