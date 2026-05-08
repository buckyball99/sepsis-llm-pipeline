import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# model_config.json fields:
# model_provider: openrouter | groq | together | deepseek | openai
# model_name: the exact model string for that provider
# api_key_env: which .env variable holds the key
# temperature: 0.0 = deterministic, higher = more creative
# max_tokens: max length of LLM response
# Older models : meta-llama/llama-3.1-70b-instruct

with open("config/model_config.json") as f:
    CONFIG = json.load(f)

PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq":       "https://api.groq.com/openai/v1",
    "together":   "https://api.together.xyz/v1",
    "deepseek":   "https://api.deepseek.com/v1",
    "openai":     "https://api.openai.com/v1",
}


def _client():
    provider = CONFIG["model_provider"]
    api_key = os.environ.get(CONFIG["api_key_env"], "")
    base_url = PROVIDER_URLS.get(provider, PROVIDER_URLS["openrouter"])
    return OpenAI(api_key=api_key, base_url=base_url)


def extract(system_prompt: str, user_content: str) -> dict | list:
    """
    Core LLM call for structured JSON extraction.
    Forces JSON output mode. Returns parsed dict/list.
    """
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
    return json.loads(raw)


def generate_sql(schema_desc: str, query: str) -> str:
    """
    Ask the LLM to convert a natural language query into DuckDB SQL.
    Returns raw SQL string (no markdown fences).
    """
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
    # Strip markdown fences if model ignores instruction
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql
