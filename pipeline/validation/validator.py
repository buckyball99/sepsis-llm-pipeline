from pipeline.validation.schemas import EvidenceRecord
from pydantic import ValidationError


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