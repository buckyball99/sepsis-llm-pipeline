# Sepsis Atlas - AI-Powered Clinical Evidence Pipeline

> **Transforming sepsis research into structured, queryable clinical intelligence.**

Sepsis Atlas is an end-to-end AI pipeline that ingests peer-reviewed sepsis research PDFs, extracts structured predictor–outcome associations using large language models, validates them against clinical plausibility rules, and makes them instantly queryable through natural language — with every extracted value traceable to its exact source sentence.

---

## The Problem

Sepsis research is vast, fragmented, and locked inside thousands of PDFs. Clinicians and researchers spend enormous time manually synthesizing evidence across studies to answer critical questions like *"What laboratory predictors are most associated with 28-day mortality in septic shock?"*

Sepsis Atlas solves this by automating the full evidence extraction and retrieval workflow — from raw PDF to structured, clinically validated, queryable knowledge.

---

## Key Features

| Feature | Description |
|---|---|
| **Automated PDF Ingestion** | Parse and chunk sepsis research papers using IBM Docling with PyMuPDF fallback |
| **LLM-Powered Extraction** | Parallel extraction of predictor–outcome associations with mandatory source traceability |
| **Clinical Validation** | Pydantic v2 schema with AUC bounds, OR/HR positivity checks, and synonym normalization |
| **Natural Language Querying** | Route queries to SQL, graph, or BM25 keyword search automatically |
| **Full Source Traceability** | Every evidence record links to its exact `source_quote` from the original paper |
| **Deduplication** | MD5-based paper hashing prevents re-ingestion of existing papers |
| **Interactive UI** | Streamlit Evidence Explorer with source verification and CSV export |
| **Admin Dashboard** | Paper management, evidence browsing, predictor summaries, and raw SQL console |
| **Docker Ready** | Single-container deployment for demos and production |

---

## Architecture

```
PDF Input
   │
   ▼
┌─────────────────────┐
│  docling_parser.py  │  IBM Docling (PyMuPDF fallback) · Markdown cache by MD5
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    chunker.py       │  3000-char chunks · 400-char overlap · Tables kept separate
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    extractor.py     │  Parallel LLM calls per chunk · GROQ / OpenRouter
│    (+ llm_client)   │  Exponential backoff · Mandatory source_quote
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    validator.py     │  Pydantic v2 · Clinical plausibility checks
│    schemas.py       │  Synonym normalization via normalisation_terms.json
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│      db.py          │  DuckDB · papers + evidence tables · Indexed on predictor/outcome
└─────────────────────┘

Query Path:
User Question → expander.py → router.py → sql_generator.py (NL→SQL, 3 retries)
                                        └→ bm25_fallback.py (keyword search on source_quote)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM Inference** | GROQ (`llama-3.3-70b-versatile`) · OpenRouter (fallback) |
| **PDF Parsing** | IBM Docling 2.93.0 · PyMuPDF |
| **Data Storage** | DuckDB |
| **Validation** | Pydantic v2 |
| **UI** | Streamlit |
| **Keyword Search** | BM25 (`rank-bm25`) |
| **Containerization** | Docker |
| **Testing** | pytest |
| **Orchestration** | Prefect |

---

## Getting Started

### Prerequisites

- Python 3.11+
- [GROQ API Key](https://console.groq.com) (primary LLM provider)
- [OpenRouter API Key](https://openrouter.ai) (fallback provider)

### Installation

```bash
git clone https://github.com/buckyball99/-sepsis-llm-pipeline.git
cd -sepsis-llm-pipeline

pip install -r requirements.txt
```

### Environment Configuration

Create a `.env` file at the project root:

```env
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

See [.env.example](.env.example) for a full template.

---

## Usage

### 1. Launch the UI

```bash
streamlit run ui/app.py
```

Opens the **Sepsis Atlas** Evidence Explorer at `http://localhost:8501`.

### 2. Ingest Research Papers

```bash
# Ingest a single PDF
python flows/ingest_flow.py path/to/paper.pdf

# Ingest all PDFs in data/raw_pdfs/
python flows/ingest_flow.py
```

The pipeline deduplicates by MD5 hash — re-running on an already-ingested paper is a no-op.

### 3. Query via CLI

```bash
python flows/query_flow.py "What predicts 28-day mortality in septic shock?"
```

### 4. Example Queries

| Query | Route |
|---|---|
| *What laboratory markers predict 28-day mortality?* | SQL |
| *Which predictors have AUC > 0.75?* | SQL |
| *Studies reporting lactate as a predictor* | SQL |
| *Find source evidence for SOFA score outcomes* | BM25 |

---

## Docker Deployment

```bash
docker build -t sepsis-llm .

docker run -p 8501:8501 -p 8000:8000 \
  -e GROQ_API_KEY=your_key \
  -e OPENROUTER_API_KEY=your_key \
  sepsis-llm
```

---

## Project Structure

```
├── config/
│   ├── model_config.json          # LLM provider, model, temperature settings
│   ├── settings.py                # Global paths and pipeline constants
│   ├── medical_terms.json         # ~40 clinical synonym groups for query expansion
│   └── normalisation_terms.json   # Canonical term mappings for storage normalization
│
├── data/
│   ├── raw_pdfs/                  # Input research papers (25+ PDFs)
│   └── processed/                 # MD5-keyed markdown cache (avoids re-parsing)
│
├── flows/
│   ├── ingest_flow.py             # End-to-end PDF ingestion orchestration
│   └── query_flow.py              # Natural language query orchestration
│
├── pipeline/
│   ├── ingestion/
│   │   ├── docling_parser.py      # PDF → Markdown (IBM Docling + PyMuPDF fallback)
│   │   └── chunker.py             # Chunking with table/figure separation
│   ├── extraction/
│   │   ├── extractor.py           # Parallel LLM extraction per chunk
│   │   ├── llm_client.py          # GROQ/OpenRouter wrapper with backoff
│   │   └── prompts.py             # System prompts (source_quote required)
│   ├── validation/
│   │   ├── schemas.py             # EvidenceRecord Pydantic v2 model
│   │   └── validator.py           # Clinical plausibility + normalization
│   ├── storage/
│   │   ├── db.py                  # DuckDB CRUD operations
│   │   └── schema.sql             # papers + evidence table definitions
│   └── query/
│       ├── router.py              # LLM-based query classification (sql/graph/text)
│       ├── expander.py            # Medical synonym expansion
│       ├── sql_generator.py       # NL → DuckDB SQL (3 retries)
│       ├── bm25_fallback.py       # Keyword search over source_quote
│       └── graph_layer.py         # Relationship-based queries
│
├── ui/
│   ├── app.py                     # Streamlit Evidence Explorer
│   ├── pages/admin.py             # Admin dashboard (paper mgmt, SQL console)
│   └── components/                # Reusable UI components
│
├── tests/
│   ├── test_extraction.py
│   ├── test_sql_generation.py
│   └── test_validation.py
│
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Database Schema

The DuckDB database (`data/sepsis_evidence.db`) stores two tables:

**`papers`** — Paper-level metadata
- `paper_id` (MD5 hash), `title`, `authors`, `year`, `journal`, `doi`, `study_type`, `ingested_at`

**`evidence`** — Structured predictor–outcome records
- Identity: `record_id` (UUID), `paper_id` (FK), `study_label`
- Clinical: `predictor`, `outcome`, `predictor_timing`, `outcome_timing`, `patient_population`, `study_setting`
- Statistics: `auc`, `odds_ratio`, `hazard_ratio`, `p_value`, `confidence_interval`, `sample_size`
- Traceability: `source_quote`, `source_location`, `confidence`, `warnings`

Indices are maintained on `predictor`, `outcome`, and `paper_id` for query performance.

---

## Design Principles

1. **Source Traceability First** — `source_quote` is a mandatory field in every `EvidenceRecord`. Every statistical claim links to its exact sentence from the source paper.

2. **Clinical Plausibility Checks** — AUC values outside [0, 1], negative odds/hazard ratios, and suspicious source quotes are flagged with warnings before storage.

3. **Graceful Degradation** — GROQ rate limits trigger exponential backoff (base 5s, max 60s, 5 attempts). OpenRouter serves as a live fallback. BM25 handles queries that fail SQL routing.

4. **Deduplication by Default** — Papers are keyed by MD5 hash. The same PDF can be re-dropped into `data/raw_pdfs/` without creating duplicate records.

---

## Running Tests

```bash
pytest tests/
```

---

## Configuration Reference

| File | Purpose |
|---|---|
| `config/model_config.json` | Switch LLM provider, model, or adjust temperature |
| `config/settings.py` | Adjust chunk size, overlap, DB path, or `TEST_MODE` |
| `config/medical_terms.json` | Add clinical synonym groups for query expansion |
| `config/normalisation_terms.json` | Add canonical mappings for storage normalization |

**TEST_MODE** (in `config/settings.py`) can limit pipeline stages to `db`, `parse`, `extract`, `validate`, `query`, or `full` — useful for development and debugging.

---

## Contributing

This project was developed as part of a clinical AI research initiative. Contributions, issue reports, and feedback are welcome via the [Issues](https://github.com/buckyball99/-sepsis-llm-pipeline/issues) tab.

---

## License

This project is intended for academic and research use. Please cite appropriately when using Sepsis Atlas in published work.

---

*Built with GROQ · IBM Docling · DuckDB · Streamlit · Pydantic v2*
