from pathlib import Path

# Project root — always correct regardless of where you run from
PROJECT_ROOT = Path(__file__).parent.parent

# ── Paths ────────────────────────────────────────────────
DB_PATH         = PROJECT_ROOT / "data" / "sepsis_atlas.duckdb"
RAW_PDFS_DIR    = PROJECT_ROOT / "data" / "raw_pdfs"
PROCESSED_DIR   = PROJECT_ROOT / "data" / "processed"
SCHEMA_PATH     = PROJECT_ROOT / "pipeline" / "storage" / "schema.sql"
MODEL_CONFIG    = PROJECT_ROOT / "config" / "model_config.json"
MEDICAL_TERMS   = PROJECT_ROOT / "config" / "medical_terms.json"
NORMALISATION_TERMS = PROJECT_ROOT / "config" / "normalisation_terms.json"


# ── Test settings ─────────────────────────────────────────
TEST_MODE       = "full"        # change this to switch test: db|parse|extract|validate|query|full
TEST_PDF        = RAW_PDFS_DIR / "Baloch_2022.pdf"   # update filename when you add a PDF


# ── Chunking settings ─────────────────────────────────────────
CHUNK_SIZE    = 5500
CHUNK_OVERLAP = 500

METADATA_CHARS = 3000  # chars of markdown to use for metadata extraction