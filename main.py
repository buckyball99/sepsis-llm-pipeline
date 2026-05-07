"""
Sepsis Atlas — Manual Test Runner
Run individual pipeline steps to verify each piece works before wiring together.

Usage:
    python main.py
Then change TEST_MODE at the top to switch what you're testing.
"""

import os
import sys
from dotenv import load_dotenv

from config.settings import TEST_PDF, TEST_MODE

load_dotenv()

# ─────────────────────────────────────────────
# CHANGE THIS to switch what you're testing
# Options: "db" | "parse" | "extract" | "validate" | "query" | "full"
# TEST_MODE = "db"

# # CHANGE THIS to point at a real PDF when testing parse/extract/full
# TEST_PDF = "data/raw_pdfs/your_paper.pdf"
# ─────────────────────────────────────────────


def test_db():
    """Test 1: Can we create the database and insert a fake record?"""
    print("\n=== TEST: Database ===")
    from pipeline.storage.db import init_db, insert_paper, insert_evidence, query_db

    init_db()
    print("✓ Database initialised")

    insert_paper({
        "paper_id": "test123",
        "title": "Test Paper on Sepsis",
        "authors": "Smith et al.",
        "year": 2024,
        "doi": "10.1000/test",
        "journal": "Critical Care",
        "paper_type": "observational",
    })
    print("✓ Inserted test paper")

    insert_evidence({
        "paper_id": "test123",
        "study_label": "Smith 2024",
        "predictor": "Lactate",
        "predictor_timing": "First 24h",
        "outcome": "28-day mortality",
        "method": "ROC analysis",
        "auc_value": 0.78,
        "performance": "AUC 0.78 (CI 0.72–0.93)",
        "source_location": "Results, Table 2",
        "source_quote": "ROC analysis revealed lactate as a significant predictor of 28-day mortality (AUC 0.78, 95% CI 0.72–0.93, p<0.001).",
        "confidence": "high",
        "not_reported": False,
        "warnings": [],
    })
    print("✓ Inserted test evidence record")

    print("\n--- papers table ---")
    papers_df = query_db("SELECT * FROM papers")
    print(f"Rows: {len(papers_df)}")
    print(papers_df[["paper_id", "title", "authors", "year", "paper_type"]].to_string())

    print("\n--- evidence table ---")
    evidence_df = query_db("SELECT * FROM evidence")
    print(f"Rows: {len(evidence_df)}")
    print(evidence_df[["study_label", "predictor", "outcome", "auc_value", "source_quote"]].to_string())

    print("\n--- joined (papers + evidence) ---")
    joined_df = query_db("""
        SELECT p.title, p.year, e.predictor, e.outcome, e.auc_value, e.confidence
        FROM evidence e
        JOIN papers p ON e.paper_id = p.paper_id
    """)
    print(f"Rows: {len(joined_df)}")
    print(joined_df.to_string())

def test_parse():
    """Test 2: Can Docling parse a PDF and chunk it?"""
    print("\n=== TEST: PDF Parsing ===")

    if not os.path.exists(TEST_PDF):
        print(f"✗ PDF not found: {TEST_PDF}")
        print("  Put a PDF in data/raw_pdfs/ and update TEST_PDF at the top of main.py")
        return

    # from pipeline.ingestion.docling_parser import parse_pdf
    from pipeline.ingestion.marker_parser import parse_pdf
    from pipeline.ingestion.chunker import chunk_document

    print(f"Parsing: {TEST_PDF}")
    parsed = parse_pdf(TEST_PDF)
    print(f"✓ Parsed — paper_id: {parsed['paper_id']}")
    print(f"  Markdown length: {len(parsed['markdown'])} chars")
    print(f"  Tables found: {len(parsed['tables'])}")
    print(f"\nFirst 500 chars of markdown:\n{parsed['markdown'][:500]}")

    chunks = chunk_document(parsed)
    parsed["chunks"] = chunks
    print(f"\n✓ Chunked into {len(chunks)} chunks")
    for i, c in enumerate(chunks[:3]):
        print(f"  Chunk {i+1}: type={c['type']}, chars={len(c['content'])}")
        print(f"    Preview: {c['content'][:120].strip()}...")


def test_extract():
    """Test 3: Can the LLM extract records from a chunk of text?"""
    print("\n=== TEST: LLM Extraction ===")
    from pipeline.extraction.llm_client import extract
    from pipeline.extraction.prompts import EXTRACTION_SYSTEM_PROMPT

    # Use a hardcoded passage so you don't need a PDF for this test
    test_passage = """
    Results: ROC analysis revealed lymphocyte count as a significant predictor 
    of 28-day mortality (AUC 0.78, 95% CI 0.72–0.93, sensitivity 0.9, 
    specificity 0.8, p<0.001). SOFA score was also predictive 
    (AUC 0.81, 95% CI 0.75–0.87, p<0.001). Lactate clearance did not 
    reach statistical significance (p=0.12).
    """

    print("Sending test passage to LLM...")
    result = extract(EXTRACTION_SYSTEM_PROMPT, test_passage)
    records = result.get("records", [])

    print(f"✓ Got {len(records)} records back")
    for i, r in enumerate(records):
        print(f"\n  Record {i+1}:")
        print(f"    Predictor:    {r.get('predictor')}")
        print(f"    Outcome:      {r.get('outcome')}")
        print(f"    AUC:          {r.get('auc_value')}")
        print(f"    Confidence:   {r.get('confidence')}")
        print(f"    Source quote: {r.get('source_quote', '')[:80]}...")


def test_validate():
    """Test 4: Does Pydantic validation catch bad records and pass good ones?"""
    print("\n=== TEST: Validation ===")
    from pipeline.validation.validator import validate_records

    records = [
        # Good record — should pass
        {
            "paper_id": "test123",
            "study_label": "Smith 2024",
            "predictor": "Lactate",
            "outcome": "28-day mortality",
            "source_location": "Results, Table 2",
            "source_quote": "Lactate was a significant predictor (AUC 0.78, p<0.001).",
            "auc_value": 0.78,
            "confidence": "high",
            "not_reported": False,
        },
        # Bad record — AUC out of range, should warn
        {
            "paper_id": "test123",
            "study_label": "Jones 2023",
            "predictor": "SOFA",
            "outcome": "ICU mortality",
            "source_location": "Table 3",
            "source_quote": "SOFA score AUC 1.5",
            "auc_value": 1.5,
            "confidence": "high",
            "not_reported": False,
        },
        # Missing source_quote — should get low confidence warning
        {
            "paper_id": "test123",
            "study_label": "Lee 2022",
            "predictor": "Procalcitonin",
            "outcome": "28-day mortality",
            "source_location": "Results",
            "source_quote": "",
            "confidence": "high",
            "not_reported": False,
        },
    ]

    valid, failed = validate_records(records)
    print(f"\n✓ Valid: {len(valid)}  |  Failed: {len(failed)}")
    for r in valid:
        print(f"  PASS — {r['study_label']}: {r['predictor']} | warnings: {r.get('warnings')}")
    for r in failed:
        print(f"  FAIL — {r.get('study_label')}: {r.get('_validation_errors', '')[:80]}")


def test_query():
    """Test 5: Can the query layer expand, route, and generate SQL?"""
    print("\n=== TEST: Query Layer ===")

    test_queries = [
        "What predicts 28-day mortality in septic shock?",
        "Show AUC values for lactate",
        "Which studies used pip-tazo?",
    ]

    from pipeline.query.expander import expand_query
    from pipeline.query.router import route_query

    for q in test_queries:
        print(f"\nQuery: '{q}'")
        expanded = expand_query(q)
        print(f"  Expanded: {expanded[:100]}")
        route = route_query(expanded)
        print(f"  Route:    {route}")

    # Test SQL generation against whatever is in the DB
    print("\n--- SQL generation test ---")
    from pipeline.query.sql_generator import query_to_dataframe
    try:
        df, sql = query_to_dataframe("show all records with AUC above 0.7")
        print(f"✓ SQL generated and executed — {len(df)} rows returned")
        print(f"  SQL: {sql[:150]}")
    except Exception as e:
        print(f"  Note: {e}")
        print("  (This is fine if the DB is empty — run test_db first)")


def test_full():
    """Test 6: Full pipeline on a real PDF."""
    print("\n=== TEST: Full Pipeline (single paper) ===")

    if not os.path.exists(TEST_PDF):
        print(f"✗ PDF not found: {TEST_PDF}")
        print("  Update TEST_PDF at the top of main.py")
        return

    from pipeline.storage.db import init_db
    from pipeline.ingestion.docling_parser import parse_pdf
    from pipeline.ingestion.chunker import chunk_document
    from pipeline.extraction.extractor import extract_paper_metadata, extract_from_chunks
    from pipeline.validation.validator import validate_records
    from pipeline.storage.db import insert_paper, insert_evidence, query_db

    init_db()

    print("Step 1: Parsing PDF...")
    parsed = parse_pdf(TEST_PDF)
    chunks = chunk_document(parsed)
    parsed["chunks"] = chunks
    print(f"  → {len(chunks)} chunks")

    print("Step 2: Extracting metadata...")
    metadata = extract_paper_metadata(chunks[0]["content"], parsed["paper_id"])
    print(f"  → Study: {metadata.get('study_label')}")

    print("Step 3: Extracting evidence...")
    raw_records = extract_from_chunks(chunks, metadata)
    print(f"  → {len(raw_records)} raw records")

    print("Step 4: Validating...")
    valid, failed = validate_records(raw_records)
    print(f"  → {len(valid)} valid, {len(failed)} failed")

    print("Step 5: Storing...")
    insert_paper(metadata)
    for r in valid:
        insert_evidence(r)

    print("Step 6: Querying back...")
    df = query_db("SELECT study_label, predictor, outcome, auc_value, confidence FROM evidence")
    print(f"  → {len(df)} total records in DB")
    print(df.to_string())


# ─────────────────────────────────────────────
TESTS = {
    "db":       test_db,
    "parse":    test_parse,
    "extract":  test_extract,
    "validate": test_validate,
    "query":    test_query,
    "full":     test_full,
}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else TEST_MODE
    if mode not in TESTS:
        print(f"Unknown mode '{mode}'. Options: {list(TESTS.keys())}")
        sys.exit(1)
    TESTS[mode]()