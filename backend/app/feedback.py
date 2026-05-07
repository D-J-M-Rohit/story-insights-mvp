import re
import uuid
from datetime import datetime, timedelta, timezone

from .analysis_nlp import ANALYSIS_VERSION, analyze_feedback_text, safe_comment_for_storage
from .config import settings
from .request_context import current_request_id, current_trace_id

ALLOWED_FEEDBACK_TYPES = {"session", "micro"}
ALLOWED_CHANNELS = {"post_report", "in_session"}
ALLOWED_TAGS = {
    "too_fast",
    "about_right",
    "too_slow",
    "confusing",
    "clear",
    "useful",
    "not_useful",
    "engaging",
    "not_engaging",
    "uncomfortable",
    "too_intense",
    "too_generic",
    "repetitive",
    "helpful",
    "bug_report",
}
MODERATION_FLAGS = {
    "pii",
    "self_harm",
    "abuse",
    "threat",
    "bug_report",
    "excessive_length",
    "suspicious_prompt_injection",
}

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\-\s().]{7,}\d)\b")
URL_RE = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
HANDLE_RE = re.compile(r"(?<!\w)@[a-zA-Z0-9_]{2,32}\b")
JWT_RE = re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+\b")
LONG_ID_RE = re.compile(r"\b\d{8,}\b")


def normalize_tag(tag: str) -> str:
    v = (tag or "").strip().lower().replace("-", "_").replace(" ", "_")
    return v if v in ALLOWED_TAGS else ""


def validate_rating(value):
    if value is None:
        return None
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_rating") from exc
    if 1 <= ivalue <= 5:
        return ivalue
    raise ValueError("invalid_rating")


def normalize_feedback_payload(payload: dict) -> dict:
    feedback_type = (payload.get("feedback_type") or "").strip().lower()
    channel = (payload.get("channel") or "").strip().lower()
    if feedback_type not in ALLOWED_FEEDBACK_TYPES:
        raise ValueError("invalid_feedback_type")
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("invalid_channel")

    tags = [normalize_tag(t) for t in payload.get("tags", [])]
    tags = [t for t in tags if t]
    comment = payload.get("comment")
    consent_comment = bool(payload.get("consent_comment", False))
    comment_max = int(settings.FEEDBACK_COMMENT_MAX_CHARS or 300)

    if feedback_type == "micro":
        comment = None
        consent_comment = False
        rating_useful = None
        rating_engaging = None
    else:
        rating_useful = validate_rating(payload.get("rating_useful"))
        rating_engaging = validate_rating(payload.get("rating_engaging"))
        if not consent_comment:
            comment = None
        elif comment is not None:
            comment = str(comment).strip()
            if len(comment) > comment_max:
                comment = comment[:comment_max]
        if not tags and rating_useful is None and rating_engaging is None and not comment:
            raise ValueError("empty_feedback")

    return {
        "session_id": payload.get("session_id"),
        "scene_id": payload.get("scene_id"),
        "report_id": payload.get("report_id"),
        "turn": payload.get("turn"),
        "feedback_type": feedback_type,
        "channel": channel,
        "category": payload.get("category"),
        "rating_useful": rating_useful,
        "rating_engaging": rating_engaging,
        "tags_json": tags,
        "comment": comment,
        "consent_comment": consent_comment,
    }


def redact_comment(text: str | None) -> str | None:
    if not text:
        return None
    value = str(text)
    value = EMAIL_RE.sub("[email]", value)
    value = PHONE_RE.sub("[phone]", value)
    value = URL_RE.sub("[url]", value)
    value = JWT_RE.sub("[token]", value)
    value = LONG_ID_RE.sub("[id]", value)
    value = HANDLE_RE.sub("[handle]", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return None
    max_len = int(settings.FEEDBACK_COMMENT_MAX_CHARS or 300)
    return value[:max_len]


def moderate_comment(text: str | None, tags: list[str]) -> tuple[str, list[str]]:
    flags = []
    original = text or ""
    redacted = redact_comment(original) or ""
    lowered = original.lower()
    if original and redacted != original:
        flags.append("pii")
    if any(k in lowered for k in ("kill myself", "suicide", "self harm", "hurt myself")):
        flags.append("self_harm")
    if any(k in lowered for k in ("idiot", "stupid", "abuse", "hate you")):
        flags.append("abuse")
    if any(k in lowered for k in ("i will kill", "threat", "destroy you")):
        flags.append("threat")
    if "bug_report" in tags or any(k in lowered for k in ("bug", "broken", "error", "crash")):
        flags.append("bug_report")
    if any(k in lowered for k in ("ignore previous instructions", "system prompt", "developer message", "jailbreak")):
        flags.append("suspicious_prompt_injection")
    flags = [f for f in sorted(set(flags)) if f in MODERATION_FLAGS]
    return ("flagged" if flags else "clean"), flags


def build_evidence_ref(session, scene=None, report=None, traces=None) -> dict:
    traces = traces or {}
    return {
        "session_id": session.get("id"),
        "scenario": session.get("scenario"),
        "scenario_pack_id": session.get("scenario_pack_id"),
        "scene_id": (scene or {}).get("id"),
        "report_id": (report or {}).get("session_id") or (report or {}).get("id"),
        "policy_trace_id": traces.get("policy_trace_id"),
        "context_trace_id": traces.get("context_trace_id"),
        "generation_trace_id": traces.get("generation_trace_id"),
    }


def build_feedback_event(payload, current_user, session, scene=None, report=None) -> dict:
    tags = payload.get("tags_json", [])
    raw_comment = payload.get("comment") if bool(payload.get("consent_comment")) else None
    if settings.ANALYSIS_NLP_ENABLED and settings.ANALYSIS_PII_REDACTION_ENABLED:
        storage = safe_comment_for_storage(raw_comment, tags=tags)
        comment_redacted = storage.get("comment_redacted")
        analysis_json = storage.get("analysis_json") or analyze_feedback_text(None, tags=tags)
    else:
        comment_redacted = redact_comment(raw_comment)
        analysis_json = analyze_feedback_text(comment_redacted, tags=tags)
    status, flags = moderate_comment(raw_comment, tags)
    pii_types = ((analysis_json.get("pii") or {}).get("entity_types") or []) if isinstance(analysis_json, dict) else []
    if pii_types:
        flags = sorted(set(flags + ["pii"]))
    if any((t.get("key") == "technical_bug") for t in (analysis_json.get("topics") or [])):
        flags = sorted(set(flags + ["bug_report"]))
    if flags and status != "flagged":
        status = "flagged"
    return {
        "id": str(uuid.uuid4()),
        "user_id": (current_user or {}).get("id"),
        "session_id": session.get("id"),
        "scene_id": (scene or {}).get("id") or payload.get("scene_id"),
        "report_id": payload.get("report_id"),
        "turn": payload.get("turn"),
        "feedback_type": payload.get("feedback_type"),
        "channel": payload.get("channel"),
        "category": payload.get("category"),
        "rating_useful": payload.get("rating_useful"),
        "rating_engaging": payload.get("rating_engaging"),
        "tags_json": tags,
        "comment": raw_comment,
        "comment_redacted": comment_redacted,
        "consent_comment": bool(payload.get("consent_comment")),
        "moderation_status": status,
        "moderation_flags_json": flags,
        "analysis_json": analysis_json if isinstance(analysis_json, dict) else {"version": ANALYSIS_VERSION},
        "evidence_ref_json": build_evidence_ref(session=session, scene=scene, report=report),
        "trace_id": current_trace_id(),
        "request_id": current_request_id(),
        "created_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewer_note": None,
    }


def build_feedback_profile(events: list[dict], current_turn: int) -> dict:
    ttl = int(settings.FEEDBACK_STYLE_HINT_TTL_TURNS or 2)
    hints = {}
    expires = current_turn
    for event in reversed(events or []):
        if event.get("feedback_type") != "micro":
            continue
        turn = int(event.get("turn") or 0)
        if turn + ttl < current_turn:
            continue
        tags = set(event.get("tags_json") or [])
        if "too_fast" in tags:
            hints["pace"] = "slower"
        elif "too_slow" in tags:
            hints["pace"] = "faster"
        elif "about_right" in tags:
            hints["pace"] = "about_right"
        if "confusing" in tags:
            hints["clarity"] = "more_explicit"
        elif "clear" in tags:
            hints["clarity"] = "ok"
        if "too_intense" in tags or "uncomfortable" in tags:
            hints["tone"] = "calmer"
        if "repetitive" in tags:
            hints["variety"] = "more_varied"
        expires = max(expires, turn + ttl)
        break
    if not hints:
        return {}
    return {"hints": hints, "expires_after_turn": expires}


def sanitize_feedback_event(event: dict, include_comment: bool = False) -> dict:
    if not event:
        return {}
    out = {
        "id": event.get("id"),
        "session_id": event.get("session_id"),
        "scene_id": event.get("scene_id"),
        "report_id": event.get("report_id"),
        "turn": event.get("turn"),
        "feedback_type": event.get("feedback_type"),
        "channel": event.get("channel"),
        "category": event.get("category"),
        "rating_useful": event.get("rating_useful"),
        "rating_engaging": event.get("rating_engaging"),
        "tags": event.get("tags_json") or [],
        "consent_comment": bool(event.get("consent_comment")),
        "moderation_status": event.get("moderation_status"),
        "moderation_flags": event.get("moderation_flags_json") or [],
        "analysis": event.get("analysis_json") or {"version": ANALYSIS_VERSION},
        "created_at": event.get("created_at"),
    }
    if include_comment and event.get("moderation_status") in {"clean", "redacted"}:
        out["comment_redacted"] = event.get("comment_redacted")
    retention_days = int(settings.FEEDBACK_RAW_RETENTION_DAYS or 90)
    created = event.get("created_at")
    if isinstance(created, str):
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            created_dt = datetime.now(timezone.utc)
    else:
        created_dt = created or datetime.now(timezone.utc)
    out["raw_retention_until"] = (created_dt + timedelta(days=retention_days)).date().isoformat()
    return out
