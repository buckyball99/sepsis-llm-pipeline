from pipeline.extraction.llm_client import extract

ROUTER_PROMPT = """Classify this clinical database query into exactly one category.

Categories:
- "sql": asks for specific numbers, statistics, comparisons, filters, or aggregations across studies
- "graph": asks about relationships between multiple entities (e.g. which drugs appeared in studies that also reported lymphocyte count)
- "text": asks for methodology, narrative explanation, qualitative synthesis, or interpretation

Return JSON only — no other text:
{"type": "sql", "reasoning": "one sentence explaining why"}"""


def route_query(query: str) -> str:
    """Returns 'sql', 'graph', or 'text'."""
    try:
        result = extract(ROUTER_PROMPT, query)
        route = result.get("type", "sql")
        if route not in ("sql", "graph", "text"):
            return "sql"
        return route
    except Exception as e:
        print(f"[router] Routing failed ({e}), defaulting to sql")
        return "sql"
    
    