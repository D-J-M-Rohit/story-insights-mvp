import re

from .config import settings
from .privacy_scrub import apply_pii_redactions, find_pii_entities

ANALYSIS_VERSION = "analysis_nlp_v1"

TOPIC_TAXONOMY = {
    "pace": {
        "label": "Pacing",
        "keywords": ["too fast", "too slow", "pace", "pacing", "rushed", "slow", "speed"],
    },
    "clarity": {
        "label": "Clarity",
        "keywords": ["confusing", "clear", "unclear", "understand", "hard to follow", "explain"],
    },
    "engagement": {
        "label": "Engagement",
        "keywords": ["engaging", "boring", "interesting", "fun", "repetitive", "generic"],
    },
    "report_usefulness": {
        "label": "Report usefulness",
        "keywords": ["useful", "helpful", "not useful", "insightful", "report", "summary"],
    },
    "scenario_realism": {
        "label": "Scenario realism",
        "keywords": ["realistic", "unrealistic", "believable", "scenario", "story"],
    },
    "emotional_intensity": {
        "label": "Emotional intensity",
        "keywords": ["intense", "stressful", "uncomfortable", "calm", "pressure"],
    },
    "fairness_ethics": {
        "label": "Fairness / ethics",
        "keywords": ["fair", "unfair", "ethical", "bias", "privacy", "safe"],
    },
    "technical_bug": {
        "label": "Technical issue",
        "keywords": ["bug", "broken", "error", "crash", "stuck", "loading", "failed"],
    },
}

POSITIVE_WORDS = {
    "helpful",
    "useful",
    "clear",
    "engaging",
    "interesting",
    "good",
    "great",
    "accurate",
    "smooth",
    "realistic",
    "insightful",
    "easy",
    "liked",
}

NEGATIVE_WORDS = {
    "confusing",
    "unclear",
    "boring",
    "bad",
    "broken",
    "error",
    "slow",
    "rushed",
    "uncomfortable",
    "repetitive",
    "generic",
    "inaccurate",
    "frustrating",
    "hard",
    "failed",
}

TAG_TOPIC_MAP = {
    "too_fast": "pace",
    "too_slow": "pace",
    "confusing": "clarity",
    "clear": "clarity",
    "helpful": "report_usefulness",
    "bug_report": "technical_bug",
    "uncomfortable": "emotional_intensity",
    "repetitive": "engagement",
    "too_generic": "engagement",
}


def preprocess_text(text: str | None, max_chars: int | None = None) -> dict:
    if not text:
        return {"clean_text": "", "length": 0, "token_count": 0, "was_truncated": False}
    clean = re.sub(r"[\x00-\x1F\x7F]", " ", str(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    limit = int(max_chars or settings.ANALYSIS_COMMENT_MAX_CHARS or 300)
    was_truncated = len(clean) > limit
    if was_truncated:
        clean = clean[:limit]
    tokens = re.findall(r"\b\w+\b", clean)
    return {
        "clean_text": clean,
        "length": len(clean),
        "token_count": len(tokens),
        "was_truncated": was_truncated,
    }


def detect_pii_entities(text: str) -> list[dict]:
    """Backward-compatible name for NLP pipeline (uses shared privacy_scrub finder)."""
    return find_pii_entities(text or "")


def redact_pii(text: str | None) -> dict:
    pre = preprocess_text(text)
    clean_text = pre["clean_text"]
    entities = find_pii_entities(clean_text)
    if not entities:
        return {"redacted_text": clean_text, "has_pii": False, "entity_types": [], "entity_counts": {}}
    redacted, counts = apply_pii_redactions(clean_text, entities)
    return {
        "redacted_text": redacted,
        "has_pii": True,
        "entity_types": sorted(counts.keys()),
        "entity_counts": counts,
    }


def extract_topic_tags(text: str | None, existing_tags: list[str] | None = None) -> list[dict]:
    if not settings.ANALYSIS_TOPIC_TAGS_ENABLED:
        return []
    existing_tags = [str(t).strip().lower() for t in (existing_tags or []) if str(t).strip()]
    redacted = redact_pii(text)
    lower = (redacted.get("redacted_text") or "").lower()
    topic_sources: dict[str, set[str]] = {}

    for tag in existing_tags:
        mapped = TAG_TOPIC_MAP.get(tag)
        if mapped:
            topic_sources.setdefault(mapped, set()).add("tag")
    for key, meta in TOPIC_TAXONOMY.items():
        for keyword in meta.get("keywords", []):
            if keyword.lower() in lower:
                topic_sources.setdefault(key, set()).add("keyword")
                break
    topics = []
    for key, sources in topic_sources.items():
        if "tag" in sources and "keyword" in sources:
            confidence = 0.8
            source = "both"
        elif "tag" in sources:
            confidence = 0.7
            source = "tag"
        else:
            confidence = 0.6
            source = "keyword"
        topics.append({"key": key, "label": TOPIC_TAXONOMY[key]["label"], "confidence": confidence, "source": source})
    topics.sort(key=lambda t: (t["confidence"], t["key"]), reverse=True)
    return topics[:5]


def detect_sentiment(text: str | None) -> dict:
    if not settings.ANALYSIS_SENTIMENT_ENABLED or not text:
        return {"label": "neutral", "score": 0.0, "confidence": 0.0}
    lower = preprocess_text(text)["clean_text"].lower()
    tokens = re.findall(r"\b[a-z']+\b", lower)
    if not tokens:
        return {"label": "neutral", "score": 0.0, "confidence": 0.0}

    score = 0.0
    intensifiers = {"very", "really", "extremely"}
    negators = {"not", "no", "never"}
    for idx, token in enumerate(tokens):
        prev = tokens[idx - 1] if idx > 0 else ""
        prev2 = tokens[idx - 2] if idx > 1 else ""
        intensity = 1.25 if prev in intensifiers or prev2 in intensifiers else 1.0
        negate = prev in negators or prev2 in negators
        if token in POSITIVE_WORDS:
            score += (-1.0 if negate else 1.0) * intensity
        elif token in NEGATIVE_WORDS:
            score += (1.0 if negate else -1.0) * intensity

    normalized = 0.0 if score == 0 else max(-1.0, min(1.0, score / max(3.0, len(tokens) / 2.0)))
    if normalized >= 0.25:
        label = "positive"
    elif normalized <= -0.25:
        label = "negative"
    else:
        label = "neutral"
    confidence = min(1.0, 0.4 + abs(normalized) * 0.6) if normalized != 0 else 0.5
    return {"label": label, "score": round(normalized, 3), "confidence": round(confidence, 3)}


def analyze_feedback_text(comment: str | None, tags: list[str] | None = None) -> dict:
    pre = preprocess_text(comment)
    redacted = redact_pii(pre["clean_text"])
    topics = extract_topic_tags(redacted.get("redacted_text"), existing_tags=tags)
    sentiment = detect_sentiment(redacted.get("redacted_text"))
    return {
        "version": ANALYSIS_VERSION,
        "preprocessed": {
            "length": pre["length"],
            "token_count": pre["token_count"],
            "was_truncated": pre["was_truncated"],
        },
        "pii": {
            "has_pii": redacted["has_pii"],
            "entity_types": redacted["entity_types"],
            "entity_counts": redacted["entity_counts"],
        },
        "topics": topics,
        "sentiment": sentiment,
    }


def safe_comment_for_storage(comment: str | None, tags: list[str] | None = None) -> dict:
    pre = preprocess_text(comment)
    redacted = redact_pii(pre["clean_text"])
    analysis = analyze_feedback_text(pre["clean_text"], tags=tags)
    return {"comment_redacted": redacted["redacted_text"] or None, "analysis_json": analysis}
