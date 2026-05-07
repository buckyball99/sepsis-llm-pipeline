import json
from pipeline.extraction.llm_client import extract

with open("config/medical_terms.json") as f:
    SYNONYMS = json.load(f)

EXPANSION_PROMPT = """You are a medical terminology expert for sepsis research.
A user has entered a clinical query. Expand it to include all relevant synonyms
and abbreviations from this dictionary so that SQL ILIKE searches will find matches.

Dictionary:
{dictionary}

Return JSON only:
{{
  "expanded_query": "rewritten query with all synonyms included using OR-style phrasing",
  "added_terms": ["list", "of", "added", "terms"]
}}"""


def expand_query(query: str) -> str:
    """Expand a clinical query with synonyms. Falls back to original on failure."""
    try:
        result = extract(
            EXPANSION_PROMPT.format(dictionary=json.dumps(SYNONYMS, indent=2)),
            query,
        )
        expanded = result.get("expanded_query", query)
        added = result.get("added_terms", [])
        if added:
            print(f"  [expander] Added terms: {added}")
        return expanded
    except Exception as e:
        print(f"  [expander] Expansion failed ({e}), using original query")
        return query
    