import json

from .config import settings


def bucket(score):
    if score < 35:
        return "low"
    if score < 65:
        return "balanced"
    return "high"


TRAIT_LABELS = {
    "adq": {
        "low": "needs more support under pressure",
        "balanced": "steady under pressure",
        "high": "adaptive under pressure",
    },
    "cdi": {
        "low": "direct decision style",
        "balanced": "reflective decision style",
        "high": "deliberative but potentially conflicted",
    },
    "risk_tolerance": {
        "low": "cautious action style",
        "balanced": "measured risk style",
        "high": "bold action style",
    },
    "social_influence_sensitivity": {
        "low": "independent decision style",
        "balanced": "balanced social awareness",
        "high": "collaborative decision style",
    },
    "time_pressure_resilience": {
        "low": "slower under deadlines",
        "balanced": "moderate deadline resilience",
        "high": "strong deadline resilience",
    },
    "consistency": {
        "low": "context-sensitive decision pattern",
        "balanced": "moderately stable decision pattern",
        "high": "stable decision pattern",
    },
    "engagement": {
        "low": "limited interaction signal",
        "balanced": "steady participation",
        "high": "active exploration",
    },
}


def build_trait_buckets(report):
    result = []
    features = report.get("features", [])
    for feature in features:
        key = feature.get("key")
        if key not in TRAIT_LABELS:
            continue
        score = float(feature.get("score", 0))
        score_bucket = bucket(score)
        result.append(
            {
                "key": key,
                "score": round(score, 2),
                "bucket": score_bucket,
                "label": TRAIT_LABELS[key][score_bucket],
            }
        )
    return result


def deterministic_interpretation(report, scenario):
    trait_buckets = build_trait_buckets(report)
    labels = [tb["label"] for tb in trait_buckets[:4]]
    strengths = [tb["label"] for tb in trait_buckets if tb["bucket"] == "high"][:2]
    growth = [tb["label"] for tb in trait_buckets if tb["bucket"] == "low"][:2]
    return {
        "decision_style": (
            f"Your pattern in this {scenario} scenario is experimental reflection only. "
            f"It looks mostly like: {', '.join(labels) if labels else 'a mixed style'}."
        ),
        "strengths": (
            f"Potential strengths include {', '.join(strengths)}."
            if strengths
            else "You show a balanced profile with no single dominant strength signal."
        ),
        "growth_areas": (
            f"Possible growth area: {', '.join(growth)}."
            if growth
            else "No clear low bucket appears; continue practicing under varied constraints."
        ),
        "setting_specific_summary": (
            "In this setting, your choices suggest a contextual style that can change with pressure and social cues. "
            "This is experimental reflection only and not a clinical, diagnostic, or hiring result."
        ),
        "trait_buckets": trait_buckets,
        "generated_by": "fallback",
    }


def llm_interpretation(report, scenario):
    if not settings.REPORT_LLM_SUMMARY_ENABLED:
        return None
    provider = (settings.LLM_PROVIDER or "mock").lower()
    if provider == "mock":
        return None

    trait_buckets = build_trait_buckets(report)
    prompt_payload = {
        "scenario": scenario,
        "metrics": trait_buckets,
        "instructions": {
            "output": "JSON only",
            "length": "Each field 1 to 3 sentences",
            "disclaimer": "experimental reflection only",
            "forbidden_terms": [
                "diagnosis",
                "disorder",
                "fit for job",
                "mental health condition",
                "clinical result",
            ],
        },
    }
    prompt = (
        "You are writing a safe, friendly report explanation.\n"
        "Use only provided scenario and metrics.\n"
        "Do not invent or alter scores.\n"
        "Return ONLY JSON with keys: decision_style, strengths, growth_areas, setting_specific_summary.\n\n"
        f"{json.dumps(prompt_payload)}"
    )
    try:
        text = ""
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.responses.create(model=settings.OPENAI_MODEL, input=prompt)
            text = getattr(response, "output_text", "") or str(response)
        elif provider == "gemini":
            from google import genai

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            text = response.text or ""
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < 0:
            return None
        parsed = json.loads(text[start : end + 1])
        required = {"decision_style", "strengths", "growth_areas", "setting_specific_summary"}
        if not required.issubset(set(parsed.keys())):
            return None
        parsed["trait_buckets"] = trait_buckets
        parsed["generated_by"] = "llm"
        return parsed
    except Exception:
        return None


def generate_interpretation(report, scenario):
    llm_value = llm_interpretation(report, scenario)
    if llm_value:
        return llm_value
    return deterministic_interpretation(report, scenario)
