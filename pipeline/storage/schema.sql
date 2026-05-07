CREATE TABLE IF NOT EXISTS papers (
    paper_id        VARCHAR PRIMARY KEY,
    title           VARCHAR,
    authors         VARCHAR,
    year            INTEGER,
    doi             VARCHAR,
    journal         VARCHAR,
    paper_type      VARCHAR,
    ingested_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id         VARCHAR PRIMARY KEY,
    paper_id            VARCHAR REFERENCES papers(paper_id),
    study_label         VARCHAR,

    population_desc     VARCHAR,
    sample_size         VARCHAR,
    setting             VARCHAR,
    country             VARCHAR,

    predictor           VARCHAR,
    predictor_timing    VARCHAR,
    outcome             VARCHAR,
    method              VARCHAR,

    effect_size         VARCHAR,
    performance         VARCHAR,

    auc_value           FLOAT,
    odds_ratio          FLOAT,
    hazard_ratio        FLOAT,
    p_value             FLOAT,
    confidence_interval VARCHAR,

    source_location     VARCHAR,
    source_quote        TEXT,

    notes               TEXT,
    confidence          VARCHAR DEFAULT 'high',
    not_reported        BOOLEAN DEFAULT FALSE,
    extraction_warnings TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_predictor ON evidence(predictor);
CREATE INDEX IF NOT EXISTS idx_evidence_outcome ON evidence(outcome);
CREATE INDEX IF NOT EXISTS idx_evidence_paper ON evidence(paper_id);