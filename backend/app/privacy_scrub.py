"""Shared pattern-based redaction for logs, traces, and NLP. No external deps."""

from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any

PII_PLACEHOLDERS = {
    "email": "[email]",
    "phone": "[phone]",
    "url": "[url]",
    "handle": "[handle]",
    "jwt": "[token]",
    "bearer_token": "[token]",
    "api_key": "[secret]",
    "database_url": "[database_url]",
    "ip_address": "[ip]",
    "ssn": "[ssn]",
    "long_numeric_id": "[id]",
}

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s().]{8,}\d)")
URL_RE = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
HANDLE_RE = re.compile(r"(?<!\w)@[a-zA-Z0-9_]{2,32}\b")
JWT_RE = re.compile(r"\beyJ[a-zA-Z0-9_-]{5,}\.[a-zA-Z0-9._-]{5,}\.[a-zA-Z0-9._-]{5,}\b")
BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._\-~+/=]{10,}\b", re.IGNORECASE)
API_KEY_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{16,}|OPENAI_API_KEY\s*[=:]\s*[A-Za-z0-9_\-]{10,})\b"
)
DB_URL_RE = re.compile(r"\b(?:postgresql(?:\+psycopg)?|mysql|mongodb|redis)://[^\s]+", re.IGNORECASE)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
LONG_NUMERIC_ID_RE = re.compile(r"\b\d{8,}\b")

_STRING_KEY_HINTS = (
    "password",
    "token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "email",
    "jwt",
    "credential",
    "openai",
    "database_url",
    "prompt",
    "scene",
    "report",
    "telemetry",
)


def _collect_entities(pattern, text: str, entity_type: str) -> list[dict]:
    entities = []
    for match in pattern.finditer(text):
        value = match.group(0)
        if entity_type == "phone":
            digits = re.sub(r"\D", "", value)
            if len(digits) < 10:
                continue
        entities.append(
            {"type": entity_type, "start": match.start(), "end": match.end(), "replacement": PII_PLACEHOLDERS[entity_type]}
        )
    return entities


def find_pii_entities(text: str) -> list[dict]:
    if not text:
        return []
    entities = []
    entities.extend(_collect_entities(EMAIL_RE, text, "email"))
    entities.extend(_collect_entities(PHONE_RE, text, "phone"))
    entities.extend(_collect_entities(URL_RE, text, "url"))
    entities.extend(_collect_entities(HANDLE_RE, text, "handle"))
    entities.extend(_collect_entities(JWT_RE, text, "jwt"))
    entities.extend(_collect_entities(BEARER_RE, text, "bearer_token"))
    entities.extend(_collect_entities(API_KEY_RE, text, "api_key"))
    entities.extend(_collect_entities(DB_URL_RE, text, "database_url"))
    entities.extend(_collect_entities(IP_RE, text, "ip_address"))
    entities.extend(_collect_entities(SSN_RE, text, "ssn"))
    entities.extend(_collect_entities(LONG_NUMERIC_ID_RE, text, "long_numeric_id"))
    entities.sort(key=lambda e: (e["start"], -(e["end"] - e["start"])))
    merged = []
    cursor = -1
    for entity in entities:
        if entity["start"] < cursor:
            continue
        merged.append(entity)
        cursor = entity["end"]
    return merged


def scrub_sensitive_text(text: str | None) -> str:
    if text is None:
        return ""
    raw = str(text)
    clean = re.sub(r"[\x00-\x1F\x7F]", " ", raw)
    entities = find_pii_entities(clean)
    if not entities:
        return clean
    parts = []
    last = 0
    for entity in entities:
        parts.append(clean[last : entity["start"]])
        parts.append(entity["replacement"])
        last = entity["end"]
    parts.append(clean[last:])
    return "".join(parts)


def redact_sensitive(obj: Any) -> Any:
    """Deep-copy and redact: sensitive keys -> [REDACTED]; string values pattern-scrubbed."""

    def _walk(value):
        if isinstance(value, dict):
            output = {}
            for key, nested in value.items():
                lk = str(key).lower()
                if any(token in lk for token in _STRING_KEY_HINTS):
                    output[key] = "[REDACTED]"
                else:
                    output[key] = _walk(nested)
            return output
        if isinstance(value, list):
            return [_walk(item) for item in value]
        if isinstance(value, str):
            return scrub_sensitive_text(value)
        return value

    return _walk(copy.deepcopy(obj))


def apply_pii_redactions(text: str, entities: list[dict]) -> tuple[str, dict[str, int]]:
    if not entities:
        return text, {}
    parts = []
    last = 0
    counts: Counter = Counter()
    for entity in entities:
        parts.append(text[last : entity["start"]])
        parts.append(entity["replacement"])
        last = entity["end"]
        counts[entity["type"]] += 1
    parts.append(text[last:])
    return "".join(parts), dict(counts)
