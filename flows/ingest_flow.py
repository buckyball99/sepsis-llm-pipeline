import os
import sys
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

# Make sure project root is on the path when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.ingestion.docling_parser import parse_pdf
from pipeline.ingestion.chunker import chunk_document
from pipeline.extraction.extractor import extract_paper_metadata, extract_from_chunks
from pipeline.validation.validator import validate_records
from pipeline.storage.db import init_db, insert_paper, insert_evidence, paper_exists

MAX_PARALLEL_PDFS = 3  # number of PDFs processed concurrently
BATCH_SIZE = 3

def _is_already_ingested(pdf_path: str) -> bool:
    """Check if a PDF has already been ingested by looking up its paper_id."""
    paper_id = hashlib.md5(pdf_path.encode()).hexdigest()
    return paper_exists(paper_id)


def ingest_paper(pdf_path: str, skip_existing: bool = True) -> int:
    """
    Full ingestion pipeline for a single PDF.
    Returns the number of valid evidence records stored.
    """
    name = os.path.basename(pdf_path)

    if skip_existing and _is_already_ingested(pdf_path):
        print(f"  [skip] {name} — already ingested")
        return 0

    print(f"\n→ Ingesting: {name}")

    try:
        parsed = parse_pdf(pdf_path)
        parsed = _chunk(parsed)
        metadata = _extract_metadata(parsed)
        raw_records = extract_from_chunks(parsed["chunks"], metadata)
        valid, failed = validate_records(raw_records)
        _store(metadata, valid)

        print(f"  ✓ {name}: {len(valid)} records stored, {len(failed)} failed validation")
        return len(valid)

    except Exception as e:
        print(f"  ✗ {name}: ingestion failed — {e}")
        return 0


def _chunk(parsed: dict) -> dict:
    chunks = chunk_document(parsed)
    parsed["chunks"] = chunks
    print(f"  [chunker] {len(chunks)} chunks")
    return parsed


def _extract_metadata(parsed: dict) -> dict:
    first_chunk = parsed["chunks"][0]["content"] if parsed["chunks"] else parsed["markdown"][:3000]
    metadata = extract_paper_metadata(first_chunk, parsed["paper_id"])
    metadata["filename"] = parsed["filename"]
    print(f"  [metadata] Study label: {metadata.get('study_label')}")
    return metadata


def _store(paper_metadata: dict, valid_records: list):
    insert_paper(paper_metadata)
    for record in valid_records:
        insert_evidence(record)


def ingest_all(
    pdf_dir: str = "data/raw_pdfs/",
    skip_existing: bool = True,
    max_workers: int = MAX_PARALLEL_PDFS,
) -> dict:
    """
    Ingest all PDFs in batches.
    Returns a dict mapping pdf_path -> record count.
    """
    init_db()
 
    pdfs = [
        os.path.join(pdf_dir, f)
        for f in sorted(os.listdir(pdf_dir))
        if f.lower().endswith(".pdf")
    ]
 
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        return {}
 
    already = sum(1 for p in pdfs if skip_existing and _is_already_ingested(p))
    to_process = len(pdfs) - already
 
    print(
        f"Found {len(pdfs)} PDFs "
        f"({already} already ingested, {to_process} to process)"
    )
 
    results: dict[str, int] = {}
 
    if to_process == 0:
        print("Nothing to ingest.")
        return {p: 0 for p in pdfs}
 
    # Process in batches of 3
    for i in range(0, len(pdfs), BATCH_SIZE):
        batch = pdfs[i:i + BATCH_SIZE]
 
        print(f"\nProcessing batch {i//BATCH_SIZE + 1}:")
        for b in batch:
            print(f" - {os.path.basename(b)}")
 
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_pdf = {
                pool.submit(ingest_paper, pdf, skip_existing): pdf
                for pdf in batch
            }
 
            for future in as_completed(future_to_pdf):
                pdf = future_to_pdf[future]
 
                try:
                    results[pdf] = future.result()
                    print(f"✓ Completed: {os.path.basename(pdf)}")
                except Exception as e:
                    print(f"✗ Failed: {os.path.basename(pdf)} -> {e}")
                    results[pdf] = 0
 
    total = sum(results.values())
 
    print(
        f"\n=== Ingestion complete: "
        f"{total} total new records from {len(pdfs)} papers ==="
    )
 
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        init_db()
        ingest_paper(sys.argv[1], skip_existing=False)
    else:
        ingest_all()
