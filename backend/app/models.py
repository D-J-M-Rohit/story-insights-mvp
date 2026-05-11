import uuid
from datetime import datetime, timezone

from sqlalchemy import BIGINT, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _id():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="participant", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String, nullable=False)
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    current_turn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    scenario_pack_id: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Scene(Base):
    __tablename__ = "scenes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    scene: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    scene_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    time_limit_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Choice(Base):
    __tablename__ = "choices"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("scenes.id"), nullable=False, index=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    option_id: Mapped[str | None] = mapped_column(String, nullable=True)
    option_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    traits_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    options_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scene_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    telemetry_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    time_limit_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=45)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Report(Base):
    __tablename__ = "reports"
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), primary_key=True)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ScenarioPack(Base):
    __tablename__ = "scenario_packs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    slug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    scenario: Mapped[str] = mapped_column(String, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    pack_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, default="internal", nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class PolicyTrace(Base):
    __tablename__ = "policy_traces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    scene_id: Mapped[str | None] = mapped_column(String, ForeignKey("scenes.id"), nullable=True, index=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_pack_id: Mapped[str] = mapped_column(String, nullable=False)
    prompt_template_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    policy_version: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_snapshot: Mapped[str] = mapped_column(String, nullable=False)
    policy_input_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    policy_output_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    output_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    validation_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fallback_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ContextTrace(Base):
    __tablename__ = "context_traces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    scene_id: Mapped[str | None] = mapped_column(String, ForeignKey("scenes.id"), nullable=True, index=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scenario_pack_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    policy_trace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    context_version: Mapped[str] = mapped_column(String, default="context_v1", nullable=False)
    query_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    retrieved_fragment_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retrieval_scores_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_bundle_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    prompt_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    output_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class GenerationTrace(Base):
    __tablename__ = "generation_traces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    scene_id: Mapped[str | None] = mapped_column(String, ForeignKey("scenes.id"), nullable=True, index=True)
    turn: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    span_id: Mapped[str] = mapped_column(String, nullable=False)
    parent_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    trace_kind: Mapped[str] = mapped_column(String, default="generation", nullable=False)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    request_model: Mapped[str | None] = mapped_column(String, nullable=True)
    response_model: Mapped[str | None] = mapped_column(String, nullable=True)
    operation_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    context_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    policy_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    response_hash: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    token_usage_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String, nullable=True)
    context_version: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(String, nullable=True)
    trace_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class DerivedFeature(Base):
    __tablename__ = "derived_features"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    report_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    feature_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    feature_name: Mapped[str] = mapped_column(String, nullable=False)
    feature_score: Mapped[float] = mapped_column(Float, nullable=False)
    feature_bucket: Mapped[str] = mapped_column(String, nullable=False)
    feature_label: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String, default="exploratory", nullable=False)
    confidence_low: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_high: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_margin: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_method: Mapped[str] = mapped_column(String, default="evidence_weighted_v1", nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    components_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_choice_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scorer_version: Mapped[str] = mapped_column(String, default="scoring_v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    scene_id: Mapped[str | None] = mapped_column(String, ForeignKey("scenes.id"), nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_type: Mapped[str] = mapped_column(String, nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    rating_useful: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_engaging: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_comment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String, default="clean", nullable=False, index=True)
    moderation_flags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    analysis_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_ref_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeedbackDailyMetric(Base):
    __tablename__ = "feedback_daily_metrics"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    day: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scenario: Mapped[str | None] = mapped_column(String, nullable=True)
    scenario_pack_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String, nullable=False)
    submitted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flagged_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dismissed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_useful: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_engaging: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class FragmentEmbedding(Base):
    __tablename__ = "fragment_embeddings"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    fragment_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    fragment_type: Mapped[str] = mapped_column(String, nullable=False)
    scenario: Mapped[str | None] = mapped_column(String, nullable=True)
    scenario_pack_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_ref_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False, index=True)
    embedding_revision: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_f32: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    normalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class FaissIndexMetadata(Base):
    __tablename__ = "faiss_index_metadata"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    index_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    index_type: Mapped[str] = mapped_column(String, nullable=False)
    hnsw_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ef_construction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ef_search_default: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False)
    index_sha256: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    archived_blob_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)


class ArchivedBlob(Base):
    __tablename__ = "archived_blobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    blob_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String, nullable=False)
    bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    content_encoding: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int] = mapped_column(BIGINT, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    kms_key_id: Mapped[str | None] = mapped_column(String, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    report_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    generation_trace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
