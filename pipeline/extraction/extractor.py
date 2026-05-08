import time
import concurrent.futures
from pipeline.extraction.llm_client import extract
from pipeline.extraction.prompts import EXTRACTION_SYSTEM_PROMPT, PAPER_METADATA_PROMPT

def extract_paper_metadata(first_chunk_content: str, paper_id: str) -> dict:
    """Extract paper metadata from the first chunk."""
    try:
        # Increased to 6000 to ensure we capture abstract/title properly
        result = extract(PAPER_METADATA_PROMPT, first_chunk_content[:6000])
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

def process_chunk(chunk: dict, paper_id: str, study_label: str, paper_metadata: dict) -> list:
    """Helper function to process a single chunk with exponential backoff."""
    content = chunk.get("content", "").strip()
    if not content or len(content) < 50:
        return []

    max_retries = 4
    for attempt in range(max_retries):
        try:
            result = extract(EXTRACTION_SYSTEM_PROMPT, content)
            records = result.get("records", [])

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
            return records
            
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "rate limit" in error_msg:
                # Exponential backoff: 2s, 4s, 8s...
                sleep_time = 2 ** (attempt + 1)
                print(f"  [extractor] API Rate limited. Retrying chunk in {sleep_time}s...")
                time.sleep(sleep_time)
            elif attempt == max_retries - 1:
                print(f"  [extractor] Chunk failed permanently after {max_retries} attempts: {e}")
                return []
            else:
                time.sleep(1) # Brief pause for non-rate-limit errors
    return []

def extract_from_chunks(chunks: list[dict], paper_metadata: dict) -> list[dict]:
    """Run extraction over all chunks concurrently."""
    all_records = []
    paper_id = paper_metadata["paper_id"]
    study_label = paper_metadata.get("study_label", paper_id[:8])

    print(f"  [extractor] Processing {len(chunks)} chunks concurrently...")

    # Use max_workers=3 to speed up processing without immediately hammering the free-tier API
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(process_chunk, chunk, paper_id, study_label, paper_metadata)
            for chunk in chunks
        ]
        
        for future in concurrent.futures.as_completed(futures):
            records = future.result()
            if records:
                all_records.extend(records)
                print(f"  [extractor] → {len(records)} records extracted from a chunk")

    print(f"  [extractor] Total raw records for paper: {len(all_records)}")
    return all_records