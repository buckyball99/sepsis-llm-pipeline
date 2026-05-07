import hashlib
import os
from pathlib import Path
from docling.document_converter import DocumentConverter

converter = DocumentConverter()


def parse_pdf(pdf_path: str) -> dict:
    """
    Parse a PDF with Docling and return a structured dict.
    Caches the markdown to data/processed/ so we don't re-parse on retries.
    """
    pdf_path = str(pdf_path)
    paper_id = hashlib.md5(pdf_path.encode()).hexdigest()

    cache_path = Path("data/processed") / f"{paper_id}.md"
    os.makedirs("data/processed", exist_ok=True)

    # Use cache if available
    if cache_path.exists():
        print(f"  [parser] Using cached markdown for {os.path.basename(pdf_path)}")
        markdown = cache_path.read_text()
        return {
            "paper_id": paper_id,
            "filename": pdf_path,
            "markdown": markdown,
            "tables": [],       # tables not available from cache; re-parse if needed
            "chunks": [],
            "_doc_result": None,
        }

    print(f"  [parser] Parsing {os.path.basename(pdf_path)} with Docling...")
    result = converter.convert(pdf_path)
    doc = result.document

    markdown = doc.export_to_markdown()
    cache_path.write_text(markdown)

    tables = []
    try:
        tables = [t.export_to_markdown() for t in doc.tables]
    except Exception:
        pass

    return {
        "paper_id": paper_id,
        "filename": pdf_path,
        "markdown": markdown,
        "tables": tables,
        "chunks": [],
        "_doc_result": result,   # keep for chunker to iterate items
    }