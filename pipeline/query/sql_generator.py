import duckdb
from pipeline.extraction.llm_client import generate_sql

DB_PATH = "data/sepsis_atlas.duckdb"

SCHEMA_DESCRIPTION = """
Table: evidence
Columns:
  evidence_id VARCHAR, paper_id VARCHAR, study_label VARCHAR,
  population_desc VARCHAR, sample_size VARCHAR, setting VARCHAR, country VARCHAR,
  predictor VARCHAR, predictor_timing VARCHAR, outcome VARCHAR, method VARCHAR,
  effect_size VARCHAR, performance VARCHAR,
  auc_value FLOAT, odds_ratio FLOAT, hazard_ratio FLOAT, p_value FLOAT,
  confidence_interval VARCHAR,
  source_location VARCHAR, source_quote TEXT,
  notes TEXT, confidence VARCHAR, not_reported BOOLEAN, extraction_warnings TEXT

Table: papers
Columns:
  paper_id VARCHAR, title VARCHAR, authors VARCHAR, year INTEGER,
  doi VARCHAR, journal VARCHAR, paper_type VARCHAR, ingested_at TIMESTAMP

Notes:
- Join tables on: evidence.paper_id = papers.paper_id
- Use ILIKE '%term%' for case-insensitive text matching
- not_reported = FALSE filters out records where data wasn't in the paper
- Always SELECT study_label, source_quote so users can verify sources
"""


def query_to_dataframe(natural_language_query: str, max_retries: int = 3):
    """
    Convert a natural language clinical query to SQL, run it, return DataFrame.

    Returns:
        (df, sql) tuple

    Raises:
        RuntimeError if SQL generation fails after max_retries
    """
    last_error = None

    for attempt in range(max_retries):
        prompt = natural_language_query
        if last_error:
            prompt += f"\n\nPrevious attempt generated SQL that failed with error:\n{last_error}\nPlease fix the SQL."

        print(f"  [sql_generator] Attempt {attempt + 1}/{max_retries}")
        sql = generate_sql(SCHEMA_DESCRIPTION, prompt)
        print(f"  [sql_generator] Generated SQL:\n{sql}")

        try:
            conn = duckdb.connect(DB_PATH)
            df = conn.execute(sql).df()
            conn.close()
            return df, sql
        except Exception as e:
            last_error = str(e)
            print(f"  [sql_generator] SQL execution failed: {e}")

    raise RuntimeError(
        f"SQL generation failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )