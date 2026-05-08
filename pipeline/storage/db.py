import duckdb
import uuid
import os
from pathlib import Path

from config.settings import DB_PATH, SCHEMA_PATH

# DB_PATH = "data/sepsis_atlas.duckdb"
# SCHEMA_PATH = "pipeline/storage/schema.sql"


def get_connection():
    """Return a DuckDB connection. Creates the DB file if it doesn't exist."""
    os.makedirs("data", exist_ok=True)
    return duckdb.connect(DB_PATH)


def init_db():
    """Create tables from schema.sql. Safe to run multiple times (IF NOT EXISTS)."""
    conn = get_connection()
    schema_sql = Path(SCHEMA_PATH).read_text()
    conn.execute(schema_sql)
    conn.close()
    print(f"Database initialised at {DB_PATH}")


def insert_paper(paper_metadata: dict):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO papers (paper_id, title, authors, year, doi, journal, paper_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (paper_id) DO NOTHING
        """, [
            paper_metadata.get("paper_id"),
            paper_metadata.get("title"),
            paper_metadata.get("authors"),
            paper_metadata.get("year"),
            paper_metadata.get("doi"),
            paper_metadata.get("journal"),
            paper_metadata.get("paper_type", "unknown"),
        ])
    finally:
        conn.close()

def insert_evidence(record: dict):
    """Insert one evidence record. Generates a UUID evidence_id."""
    conn = get_connection()
    try:
        # Check for duplicate before inserting
        existing = conn.execute("""
            SELECT evidence_id FROM evidence 
            WHERE paper_id = ? 
            AND predictor = ? 
            AND outcome = ?
            AND (auc_value = ? OR (auc_value IS NULL AND ? IS NULL))
            AND (method = ? OR (method IS NULL AND ? IS NULL))    
        """, [
            record.get("paper_id"),
            record.get("predictor"),
            record.get("outcome"),
            record.get("auc_value"),
            record.get("auc_value"),
            record.get("method"),
            record.get("method"),
        ]).fetchone()
        
        if existing:
            print(f"  [db] Skipping duplicate: {record.get('predictor')} → {record.get('outcome')}")
            return

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
    finally:
        conn.close()


def query_db(sql: str):
    """Run arbitrary SQL and return a pandas DataFrame."""
    conn = get_connection()
    try:
        df = conn.execute(sql).df()
        return df
    finally:
        conn.close()
        

def clear_db():
    """Delete all rows from both tables. Keeps the schema intact."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM evidence")
        conn.execute("DELETE FROM papers")
        print("Database cleared.")
    finally:
        conn.close()
    print("Database cleared.")