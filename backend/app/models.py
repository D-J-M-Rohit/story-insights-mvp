import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
