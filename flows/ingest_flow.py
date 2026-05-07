import os
import sys
import hashlib

# Make sure project root is on the path when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefect import flow, task
from prefect.tasks import task_input_hash

from pipeline.ingestion.docling_parser import parse_pdf
from pipeline.ingestion.chunker import chunk_document
from pipeline.extraction.extractor import extract_paper_metadata, extract_from_chunks
from pipeline.validation.validator import validate_records
from pipeline.storage.db import init_db, insert_paper, insert_evidence


@task(retries=1, retry_delay_seconds=10, cache_key_fn=task_input_hash)
def task_parse_pdf(pdf_path: str) -> dict:
    print(f"[task] Parsing: {os.path.basename(pdf_path)}")
    return parse_pdf(pdf_path)


@task
def task_chunk(parsed: dict) -> dict:
    print("[task] Chunking document...")
    chunks = chunk_document(parsed)
    parsed["chunks"] = chunks
    print(f"[task] → {len(chunks)} chunks")
    return parsed


@task(retries=2, retry_delay_seconds=15)
def task_extract_metadata(parsed: dict) -> dict:
    print("[task] Extracting paper metadata...")
    first_chunk = parsed["chunks"][0]["content"] if parsed["chunks"] else parsed["markdown"][:3000]
    metadata = extract_paper_metadata(first_chunk, parsed["paper_id"])
    metadata["filename"] = parsed["filename"]
    print(f"[task] → Study label: {metadata.get('study_label')}")
    return metadata


@task(retries=2, retry_delay_seconds=15)
def task_extract_evidence(parsed: dict, paper_metadata: dict) -> list:
    print(f"[task] Extracting evidence from {len(parsed['chunks'])} chunks...")
    return extract_from_chunks(parsed["chunks"], paper_metadata)


@task
def task_validate(records: list) -> tuple:
    print(f"[task] Validating {len(records)} raw records...")
    return validate_records(records)


@task
def task_store(paper_metadata: dict, valid_records: list):
    print(f"[task] Storing {len(valid_records)} valid records...")
    insert_paper(paper_metadata)
    for record in valid_records:
        insert_evidence(record)
    print("[task] Storage complete.")


@flow(name="ingest-paper", log_prints=True)
def ingest_paper(pdf_path: str) -> int:
    """Full ingestion pipeline for a single PDF."""
    parsed        = task_parse_pdf(pdf_path)
    parsed        = task_chunk(parsed)
    metadata      = task_extract_metadata(parsed)
    raw_records   = task_extract_evidence(parsed, metadata)
    valid, failed = task_validate(raw_records)
    task_store(metadata, valid)

    print(f"\n✓ {os.path.basename(pdf_path)}: {len(valid)} records stored, {len(failed)} failed")
    return len(valid)


@flow(name="ingest-all-papers", log_prints=True)
def ingest_all(pdf_dir: str = "data/raw_pdfs/") -> dict:
    """Ingest all PDFs in the given directory."""
    init_db()

    pdfs = [
        os.path.join(pdf_dir, f)
        for f in os.listdir(pdf_dir)
        if f.endswith(".pdf")
    ]

    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        return {}

    print(f"Found {len(pdfs)} PDFs to ingest")
    results = {}
    for pdf in pdfs:
        n = ingest_paper(pdf)
        results[pdf] = n

    total = sum(results.values())
    print(f"\n=== Ingestion complete: {total} total records from {len(pdfs)} papers ===")
    return results


if __name__ == "__main__":
    # Run: python flows/ingest_flow.py
    # Or:  python flows/ingest_flow.py path/to/single.pdf
    if len(sys.argv) > 1:
        ingest_paper(sys.argv[1])
    else:
        ingest_all()
        