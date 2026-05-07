from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline.extraction.llm_client import extract
from pipeline.extraction.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    PAPER_METADATA_PROMPT,
    PHENOTYPE_EXTRACTION_PROMPT,
)

MAX_WORKERS = 5  # parallel LLM calls per paper


def extract_paper_metadata(first_chunk_content: str, paper_id: str) -> dict:
    """Extract title, authors, year etc. from the first chunk of a paper."""
    try:
        result = extract(PAPER_METADATA_PROMPT, first_chunk_content[:3000])
        result["paper_id"] = paper_id
        return result
    except Exception as e:
        print(f"  [extractor] Metadata extraction failed: {e}")
        return {
            "paper_id": paper_id,
            "title": None,
            "authors": None,
            "year": None,
            "journal": None,
            "doi": None,
            "paper_type": "unknown",
            "study_label": f"Unknown ({paper_id[:8]})",
            "population_desc": None,
            "sample_size": None,
            "setting": "unknown",
            "country": None,
        }


def _extract_chunk(chunk_idx: int, chunk: dict, paper_metadata: dict, prompt: str) -> list[dict]:
    """Process a single chunk and return a list of extracted records."""
    content = chunk.get("content", "").strip()
    if not content or len(content) < 50:
        return []

    paper_id = paper_metadata["paper_id"]
    study_label = paper_metadata.get("study_label", paper_id[:8])

    try:
        result = extract(prompt, content)
        records = (result.get("records") or []) if isinstance(result, dict) else []

        for record in records:
            record["paper_id"] = paper_id
            record["study_label"] = study_label
            if not record.get("population_desc"):
                record["population_desc"] = paper_metadata.get("population_desc")
            if not record.get("sample_size"):
                record["sample_size"] = paper_metadata.get("sample_size")
            if not record.get("setting"):
                record["setting"] = paper_metadata.get("setting")
            if not record.get("country"):
                record["country"] = paper_metadata.get("country")

        print(f"  [extractor] Chunk {chunk_idx+1}: {len(records)} records (type={chunk['type']}, chars={len(content)})")
        return records

    except Exception as e:
        print(f"  [extractor] Chunk {chunk_idx+1} failed: {e}")
        return []


def extract_from_chunks(
    chunks: list[dict],
    paper_metadata: dict,
    mode: str = "evidence",
) -> list[dict]:
    """
    Run parallel LLM extraction over all chunks of a paper.

    mode:
      "evidence"  - standard predictor-outcome extraction (default)
      "phenotype" - sepsis phenotype/cluster extraction
    """
    prompt = PHENOTYPE_EXTRACTION_PROMPT if mode == "phenotype" else EXTRACTION_SYSTEM_PROMPT

    eligible = [
        (i, chunk) for i, chunk in enumerate(chunks)
        if chunk.get("content", "").strip() and len(chunk.get("content", "")) >= 50
    ]

    print(f"  [extractor] Processing {len(eligible)}/{len(chunks)} chunks in parallel (workers={MAX_WORKERS})")

    all_records: list[dict] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_extract_chunk, i, chunk, paper_metadata, prompt): i
            for i, chunk in eligible
        }
        for future in as_completed(futures):
            records = future.result()
            all_records.extend(records)

    print(f"  [extractor] Total raw records for paper: {len(all_records)}")
    return all_records
