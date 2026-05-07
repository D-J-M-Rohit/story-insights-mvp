from app.analysis_nlp import (
    analyze_feedback_text,
    detect_sentiment,
    extract_topic_tags,
    preprocess_text,
    redact_pii,
)


def test_preprocess_none_and_whitespace_and_truncation():
    empty = preprocess_text(None)
    assert empty["clean_text"] == ""
    assert empty["token_count"] == 0
    spaced = preprocess_text("  hello \n\n world\t ")
    assert spaced["clean_text"] == "hello world"
    truncated = preprocess_text("x" * 20, max_chars=10)
    assert truncated["was_truncated"] is True
    assert truncated["length"] == 10


def test_redact_pii_detects_common_patterns():
    text = (
        "mail me at test@example.com and call +1 234-567-8910 "
        "visit https://example.com @handle "
        "Bearer abcdefghijklmnop "
        "postgresql://user:pass@localhost:5432/db "
        "ip 10.10.10.10 ssn 123-45-6789 id 123456789"
    )
    redacted = redact_pii(text)
    assert redacted["has_pii"] is True
    for marker in ("[email]", "[phone]", "[url]", "[handle]", "[token]", "[database_url]", "[ip]", "[ssn]", "[id]"):
        assert marker in redacted["redacted_text"]


def test_topics_from_text_and_tags():
    topics = extract_topic_tags("The story was too fast and confusing", existing_tags=["bug_report"])
    keys = {t["key"] for t in topics}
    assert "pace" in keys
    assert "clarity" in keys
    assert "technical_bug" in keys
    assert len(topics) <= 5
    assert extract_topic_tags("nothing recognizable", existing_tags=[]) == []


def test_sentiment_rules():
    assert detect_sentiment("This was helpful and clear")["label"] == "positive"
    assert detect_sentiment("This was confusing and frustrating")["label"] == "negative"
    assert detect_sentiment("not useful")["label"] == "negative"
    assert detect_sentiment("")["label"] == "neutral"


def test_analysis_json_has_no_raw_pii():
    analysis = analyze_feedback_text("email me foo@bar.com and call 9998887777", tags=["too_fast"])
    blob = str(analysis).lower()
    assert "foo@bar.com" not in blob
    assert "9998887777" not in blob
    assert analysis["version"] == "analysis_nlp_v1"
