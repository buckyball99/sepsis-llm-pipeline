# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An AI-powered clinical evidence pipeline that extracts, validates, and queries structured predictor-outcome associations from sepsis research PDFs. Every extracted value is traceable to its exact source sentence (`source_quote` is a mandatory field throughout).

## Commands

### Setup
```bash
pip install -r requirements.txt
```

Create a `.env` file at the project root:
```
GROQ_API_KEY=your_groq_api_key          # Primary provider
OPENROUTER_API_KEY=your_openrouter_key  # Fallback provider
```

### Run the application
```bash
streamlit run ui/app.py
```

### Ingest PDFs
```bash
# Single PDF
python flows/ingest_flow.py path/to/paper.pdf

# All PDFs in data/raw_pdfs/
python flows/ingest_flow.py
```

### Query via CLI
```bash
python flows/query_flow.py "What predicts 28-day mortality in septic shock?"
```

### Docker
```bash
docker build -t sepsis-llm .
docker run -p 8501:8501 -p 8000:8000 -e GROQ_API_KEY=your_key sepsis-llm
```

### Tests
```bash
pytest tests/
```

## Architecture

### Data flow
```
PDF → docling_parser.py → chunker.py → extractor.py (parallel LLM calls)
    → validator.py (Pydantic + clinical checks) → db.py (DuckDB)
    ↑ query_flow.py routes queries through expander.py → sql_generator.py or bm25_fallback.py
```

### Key modules

**Ingestion (`flows/ingest_flow.py`)** — orchestrates the full pipeline: parse → chunk → extract metadata → extract evidence → validate → store. Skips already-ingested papers via MD5 hash. Uses 3 parallel PDF batches with 5-worker thread pool per batch for LLM calls.

**Parsing (`pipeline/ingestion/docling_parser.py`)** — IBM Docling as primary parser with PyMuPDF fallback. Caches parsed markdown to `data/processed/` keyed by MD5 to avoid re-parsing.

**Chunking (`pipeline/ingestion/chunker.py`)** — 3000-char max chunks with 400-char overlap; tables/figures kept separate from text chunks.

**Extraction (`pipeline/extraction/`)** — `llm_client.py` wraps GROQ/OpenRouter via the OpenAI-compatible API. `extractor.py` runs parallel LLM calls per chunk. `prompts.py` contains all system prompts; every prompt mandates a `source_quote`.

**Validation (`pipeline/validation/`)** — `schemas.py` defines `EvidenceRecord` (Pydantic v2). `validator.py` normalizes synonyms via `config/normalisation_terms.json` then checks clinical plausibility (AUC < 0.5 warning, OR/HR > 0 bounds, non-empty `source_quote`).

**Storage (`pipeline/storage/`)** — DuckDB via `db.py`. Two tables: `papers` (keyed by MD5 paper_id) and `evidence` (UUID PK, foreign key to papers). Schema defined in `pipeline/storage/schema.sql`.

**Query pipeline (`pipeline/query/`)** — `router.py` classifies queries as `sql`/`graph`/`text` (LLM-based with SQL fallback). `expander.py` maps terms to synonyms from `config/medical_terms.json`. `sql_generator.py` converts NL to DuckDB SQL (3 retries). `bm25_fallback.py` provides keyword search over `source_quote` values for `text`-type queries.

**UI (`ui/app.py`, `ui/pages/admin.py`)** — Streamlit app with Evidence Explorer (query + results with source verification expanders + CSV download) and Admin Dashboard (paper management, evidence browser, predictor summary, raw SQL console).

### Configuration
- `config/model_config.json` — LLM provider, model name, temperature, max tokens
- `config/settings.py` — all file paths and constants (`CHUNK_SIZE=5500`, `CHUNK_OVERLAP=500`, `TEST_MODE`)
- `config/medical_terms.json` — query expansion synonyms (~40 clinical term groups)
- `config/normalisation_terms.json` — canonical term mappings for storage normalization

### LLM provider
Default: GROQ (`llama-3.3-70b-versatile`). Change provider/model in `config/model_config.json`. Rate limit errors trigger exponential backoff (base 5s, max 60s, max 5 attempts) in `llm_client.py`.

### Database
DuckDB at `data/sepsis_evidence.db`. The `evidence` table has indices on `predictor`, `outcome`, and `paper_id`. The Admin Dashboard exposes a read-only SQL console (enforces `SELECT`-only queries).

## Important Constraints

- `source_quote` is mandatory in every `EvidenceRecord` — prompts and the Pydantic schema both enforce this for traceability.
- Papers are deduplicated by MD5 hash of their file path; re-ingesting the same file is a no-op unless deleted from the DB first.
- The query pipeline always includes `study_label` and `source_quote` in SQL SELECT outputs.
- `TEST_MODE` in `config/settings.py` can limit pipeline stages to `db|parse|extract|validate|query|full`.
