from pipeline.validation.schemas import EvidenceRecord
from pydantic import ValidationError
import json


from config.settings import NORMALISATION_TERMS

# ── Normalisation setup ───────────────────────────────────

with open(NORMALISATION_TERMS) as f:
    NORM_TERMS = json.load(f)

# Build reverse map: any variant → canonical full name
REVERSE_MAP = {}
for canonical, synonyms in NORM_TERMS.items():
    REVERSE_MAP[canonical.lower()] = canonical  # canonical maps to itself
    for synonym in synonyms:
        # Strip whitespace on ingest to protect against messy JSON formatting
        REVERSE_MAP[synonym.lower().strip()] = canonical

def normalise_term(term: str) -> str:
    # Defensive check: if it's null, or somehow a number/boolean, return as-is
    if not term or not isinstance(term, str):
        return term
    clean_term = term.lower().strip()
    # Fallback to original (stripped) term if not found in map
    return REVERSE_MAP.get(clean_term, term.strip())

def normalise_record(record: dict) -> dict:
    record["predictor"] = normalise_term(record.get("predictor", ""))
    record["outcome"] = normalise_term(record.get("outcome", ""))
    return record

# ── Validation ────────────────────────────────────────────

def validate_records(raw_records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validate a list of raw extracted dicts against the EvidenceRecord schema.

    Returns:
        valid_records   — list of dicts ready to insert into DuckDB
        failed_records  — list of dicts that failed validation (with error info)
    """
    valid = []
    failed = []

    for i, raw in enumerate(raw_records):
        try:
            raw = normalise_record(raw)  # normalise first, then validate
            record = EvidenceRecord(**raw)
            record_dict = record.model_dump()

            if record.warnings:
                print(f"  [validator] Record {i+1} warnings: {record.warnings}")

            valid.append(record_dict)

        except ValidationError as e:
            print(f"  [validator] Record {i+1} FAILED validation: {e.error_count()} errors")
            for err in e.errors():
                print(f"    - {err['loc']}: {err['msg']}")
            raw["_validation_errors"] = str(e)
            failed.append(raw)

        except Exception as e:
            print(f"  [validator] Record {i+1} unexpected error: {e}")
            raw["_validation_errors"] = str(e)
            failed.append(raw)

    print(f"  [validator] {len(valid)} valid, {len(failed)} failed")
    return valid, failed

