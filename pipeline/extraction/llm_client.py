import json
import os
import re
import time
import random
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "model_config.json"
with open(_CONFIG_PATH) as f:
    CONFIG = json.load(f)

OPENROUTER_BASE_URL = "https://api.groq.com/openai/v1"
#OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Retry settings for 429 rate-limit errors
_MAX_RETRIES = 5
_BASE_DELAY = 5.0   # seconds
_MAX_DELAY = 60.0


def _client() -> OpenAI:
    api_key = os.environ.get(CONFIG["api_key_env"], "")
    if not api_key:
        raise EnvironmentError(
            f"API key not set. Add {CONFIG['api_key_env']} to your .env file."
        )
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def _parse_json(raw: str) -> dict | list:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "rate" in msg.lower() or "rate_limit" in msg.lower()


def _call_with_retry(fn, *args, **kwargs):
    """Call fn(*args, **kwargs) with exponential backoff on 429 errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if _is_rate_limit(e) and attempt < _MAX_RETRIES - 1:
                delay = min(_BASE_DELAY * (2 ** attempt) + random.uniform(0, 2), _MAX_DELAY)
                print(f"  [llm] Rate limited (attempt {attempt+1}/{_MAX_RETRIES}). Retrying in {delay:.1f}s...")
                time.sleep(delay)
            else:
                raise
    raise RuntimeError("Exhausted retries")


def extract(system_prompt: str, user_content: str) -> dict | list:
    """
    Core LLM call for structured JSON extraction via OpenRouter.
    Retries automatically on 429 rate-limit errors.
    """
    def _do():
        response = _client().chat.completions.create(
            model=CONFIG["model_name"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=CONFIG.get("temperature", 0.0),
            max_tokens=CONFIG.get("max_tokens", 4000),
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return _parse_json(raw)

    return _call_with_retry(_do)


def generate_sql(schema_desc: str, query: str) -> str:
    """
    Convert a natural language query into DuckDB SQL via OpenRouter.
    Returns raw SQL string (no markdown fences).
    """
    def _do():
        response = _client().chat.completions.create(
            model=CONFIG["model_name"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a DuckDB SQL expert.\n"
                        f"Schema:\n{schema_desc}\n"
                        f"Rules:\n"
                        f"- Return ONLY valid DuckDB SQL. No markdown. No explanation.\n"
                        f"- Always include study_label and source_quote columns in SELECT.\n"
                        f"- Use ILIKE for string matching (case-insensitive).\n"
                        f"- Join papers table on paper_id when title/year/doi is needed.\n"
                        f"- Use IS NOT NULL and not_reported = FALSE to filter valid records."
                    ),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.0,
        )
        sql = response.choices[0].message.content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()
        return sql

    return _call_with_retry(_do)
