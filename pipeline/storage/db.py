import duckdb
import uuid
import os
from pathlib import Path

DB_PATH = "data/sepsis_atlas.duckdb"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection():
    """Return a DuckDB connection. Creates the DB file if it doesn't exist."""
    os.makedirs("data", exist_ok=True)
    return duckdb.connect(DB_PATH)


def init_db():
    """Create tables from schema.sql. Safe to run multiple times (IF NOT EXISTS)."""
    conn = get_connection()
    conn.execute(SCHEMA_PATH.read_text())
    conn.close()
    print(f"Database initialised at {DB_PATH}")


# ── Write helpers ─────────────────────────────────────────────────────────────

def insert_paper(paper_metadata: dict):
    """Insert a row into the papers table. Skips if paper_id already exists."""
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO papers (paper_id, title, authors, year, doi, journal, paper_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        paper_metadata.get("paper_id"),
        paper_metadata.get("title"),
        paper_metadata.get("authors"),
        paper_metadata.get("year"),
        paper_metadata.get("doi"),
        paper_metadata.get("journal"),
        paper_metadata.get("paper_type", "unknown"),
    ])
    conn.close()


def insert_evidence(record: dict):
    """Insert one evidence record. Generates a UUID evidence_id."""
    conn = get_connection()
    evidence_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO evidence (
            evidence_id, paper_id, study_label,
            population_desc, sample_size, setting, country,
            predictor, predictor_timing, outcome, method,
            effect_size, performance,
            auc_value, odds_ratio, hazard_ratio, p_value, confidence_interval,
            source_location, source_quote,
            notes, confidence, not_reported, extraction_warnings
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        evidence_id,
        record.get("paper_id"),
        record.get("study_label"),
        record.get("population_desc"),
        record.get("sample_size"),
        record.get("setting"),
        record.get("country"),
        record.get("predictor"),
        record.get("predictor_timing"),
        record.get("outcome"),
        record.get("method"),
        record.get("effect_size"),
        record.get("performance"),
        record.get("auc_value"),
        record.get("odds_ratio"),
        record.get("hazard_ratio"),
        record.get("p_value"),
        record.get("confidence_interval"),
        record.get("source_location"),
        record.get("source_quote"),
        record.get("notes"),
        record.get("confidence", "high"),
        record.get("not_reported", False),
        "; ".join(record.get("warnings", [])) if record.get("warnings") else None,
    ])
    conn.close()


# ── Read helpers ──────────────────────────────────────────────────────────────

def query_db(sql: str):
    """Run arbitrary SQL and return a pandas DataFrame."""
    conn = get_connection()
    df = conn.execute(sql).df()
    conn.close()
    return df


def paper_exists(paper_id: str) -> bool:
    """Return True if a paper with this ID is already in the database."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT 1 FROM papers WHERE paper_id = ? LIMIT 1", [paper_id]
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def get_stats() -> dict:
    """Return high-level DB stats for the admin dashboard."""
    try:
        conn = get_connection()
        paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        high_conf = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE confidence = 'high'"
        ).fetchone()[0]
        not_reported = conn.execute(
            "SELECT COUNT(*) FROM evidence WHERE not_reported = TRUE"
        ).fetchone()[0]
        conn.close()
        return {
            "papers": paper_count,
            "evidence_records": evidence_count,
            "high_confidence": high_conf,
            "not_reported": not_reported,
        }
    except Exception:
        return {"papers": 0, "evidence_records": 0, "high_confidence": 0, "not_reported": 0}


def get_all_papers():
    """Return all rows in the papers table as a DataFrame."""
    return query_db(
        "SELECT paper_id, title, authors, year, journal, paper_type, ingested_at "
        "FROM papers ORDER BY ingested_at DESC"
    )


def get_evidence_for_paper(paper_id: str):
    """Return all evidence records for a given paper_id."""
    conn = get_connection()
    df = conn.execute(
        "SELECT * FROM evidence WHERE paper_id = ? ORDER BY predictor", [paper_id]
    ).df()
    conn.close()
    return df


def delete_paper(paper_id: str):
    """Delete a paper and all its evidence records."""
    conn = get_connection()
    conn.execute("DELETE FROM evidence WHERE paper_id = ?", [paper_id])
    conn.execute("DELETE FROM papers WHERE paper_id = ?", [paper_id])
    conn.close()


def get_predictor_summary():
    """Return predictor-level summary ranked by evidence count."""
    return query_db("""
        SELECT
            predictor,
            COUNT(*) AS study_count,
            ROUND(AVG(auc_value), 3) AS avg_auc,
            ROUND(AVG(odds_ratio), 3) AS avg_or,
            COUNT(CASE WHEN confidence = 'high' THEN 1 END) AS high_conf_count
        FROM evidence
        WHERE not_reported = FALSE
        GROUP BY predictor
        ORDER BY study_count DESC
    """)
