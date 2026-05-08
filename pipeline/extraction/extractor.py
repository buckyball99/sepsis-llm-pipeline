from pipeline.extraction.llm_client import extract
from pipeline.extraction.prompts import EXTRACTION_SYSTEM_PROMPT, PAPER_METADATA_PROMPT
import time 


def extract_paper_metadata(first_chunk_content: str, paper_id: str) -> dict:
    try:
        result = extract(PAPER_METADATA_PROMPT, first_chunk_content[:3000])
        
        # Handle case where LLM returns a list instead of a dict
        if isinstance(result, list):
            result = result[0] if result else {}
            
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

def extract_from_chunks(chunks: list[dict], paper_metadata: dict) -> list[dict]:
    """
    Run extraction over all chunks of a paper.
    Returns flat list of raw evidence record dicts (before Pydantic validation).
    """
    all_records = []
    paper_id = paper_metadata["paper_id"]
    study_label = paper_metadata.get("study_label", paper_id[:8])

    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "").strip()
        if not content or len(content) < 50:
            continue

        print(f"  [extractor] Chunk {i+1}/{len(chunks)} (type={chunk['type']}, chars={len(content)})")

        try:
            result = extract(EXTRACTION_SYSTEM_PROMPT, content)
            records = result.get("records", [])

            for record in records:
                record["paper_id"] = paper_id
                record["study_label"] = study_label
                # Carry over population/sample info from metadata if not set per-chunk
                if not record.get("population_desc"):
                    record["population_desc"] = paper_metadata.get("population_desc")
                if not record.get("sample_size"):
                    record["sample_size"] = paper_metadata.get("sample_size")
                if not record.get("setting"):
                    record["setting"] = paper_metadata.get("setting")
                if not record.get("country"):
                    record["country"] = paper_metadata.get("country")

            all_records.extend(records)
            print(f"  [extractor] → {len(records)} records extracted")

        except Exception as e:
            print(f"  [extractor] Chunk {i+1} failed: {e}")
            continue

        time.sleep(15)  # wait 15 seconds between chunks to stay under TPM limit

    print(f"  [extractor] Total raw records for paper: {len(all_records)}")
    return all_records