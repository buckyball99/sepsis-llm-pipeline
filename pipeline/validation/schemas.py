from pydantic import BaseModel, field_validator, model_validator
from typing import Optional


class EvidenceRecord(BaseModel):
    # Required identification
    paper_id:           str
    study_label:        str

    # Population context
    population_desc:    Optional[str] = None
    sample_size:        Optional[str] = None
    setting:            Optional[str] = None
    country:            Optional[str] = None

    # Core clinical association
    predictor:          str
    predictor_timing:   Optional[str] = None
    outcome:            str
    method:             Optional[str] = None

    # Effect size strings (kept as text to preserve full representation)
    effect_size:        Optional[str] = None
    performance:        Optional[str] = None

    # Parsed numerics for SQL filtering
    auc_value:          Optional[float] = None
    odds_ratio:         Optional[float] = None
    hazard_ratio:       Optional[float] = None
    p_value:            Optional[float] = None
    confidence_interval: Optional[str] = None

    # Traceability — mandatory
    source_location:    str = "unknown"
    source_quote:       str                     # no default — must be provided

    # Quality flags
    notes:              Optional[str] = None
    confidence:         str = "high"
    not_reported:       bool = False
    warnings:           list[str] = []

    @field_validator("auc_value")
    @classmethod
    def auc_range(cls, v):
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(f"AUC must be between 0 and 1, got {v}")
        return v

    @field_validator("odds_ratio", "hazard_ratio")
    @classmethod
    def positive_ratio(cls, v):
        if v is not None and v <= 0:
            raise ValueError("OR/HR must be positive")
        return v

    @field_validator("p_value")
    @classmethod
    def p_value_range(cls, v):
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(f"p-value must be between 0 and 1, got {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def valid_confidence(cls, v):
        if v not in ("high", "medium", "low"):
            return "low"
        return v

    @model_validator(mode="after")
    def sanity_checks(self):
        """Clinical plausibility checks — flag but don't reject."""
        if self.auc_value is not None and self.auc_value < 0.5:
            self.warnings.append(
                f"AUC below 0.5 ({self.auc_value}) — worse than random, verify extraction"
            )
        if self.source_quote and len(self.source_quote) < 10:
            self.warnings.append("Source quote is suspiciously short — verify manually")
        if not self.source_quote or self.source_quote.strip() == "":
            self.warnings.append("CRITICAL: source_quote is empty — traceability failed")
            self.confidence = "low"
        if self.odds_ratio is not None and self.odds_ratio > 100:
            self.warnings.append(f"Odds ratio very large ({self.odds_ratio}) — verify")
        if self.p_value is not None and self.auc_value is not None:
            if self.auc_value > 0.9 and self.p_value > 0.05:
                self.warnings.append(
                    "High AUC but non-significant p-value — check for inconsistency"
                )
        return self