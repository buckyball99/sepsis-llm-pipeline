import hashlib
import os
from pathlib import Path

from docling.document_converter import DocumentConverter

converter = DocumentConverter()


def parse_pdf(pdf_path: str) -> dict:
    """
    Parse a PDF with Docling and return a structured dict.
    Caches the markdown to data/processed/ to avoid re-parsing on retries.
    Falls back to plain text extraction if Docling fails.
    """
    pdf_path = str(pdf_path)
    paper_id = hashlib.md5(pdf_path.encode()).hexdigest()

    cache_path = Path("data/processed") / f"{paper_id}.md"
    os.makedirs("data/processed", exist_ok=True)

    # Use cache if available
    if cache_path.exists():
        print(f"  [parser] Using cached markdown for {os.path.basename(pdf_path)}")
        markdown = cache_path.read_text(encoding="utf-8")
        return {
            "paper_id": paper_id,
            "filename": pdf_path,
            "markdown": markdown,
            "tables": [],
            "chunks": [],
            "_doc_result": None,
        }

    print(f"  [parser] Parsing {os.path.basename(pdf_path)} with Docling...")
    try:
        result = converter.convert(pdf_path)
        doc = result.document

        markdown = doc.export_to_markdown()
        # Always write with explicit UTF-8 to avoid charmap errors on Windows
        cache_path.write_text(markdown, encoding="utf-8")

        tables = []
        try:
            tables = [t.export_to_markdown(doc=doc) for t in doc.tables]
        except Exception:
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
            "_doc_result": result,
        }

    except Exception as e:
        print(f"  [parser] Docling failed ({e}), falling back to plain text extraction...")
        return _fallback_parse(pdf_path, paper_id, cache_path)


def _fallback_parse(pdf_path: str, paper_id: str, cache_path: Path) -> dict:
    """Plain text extraction via PyMuPDF (fitz) when Docling fails."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()

        markdown = "\n\n---\n\n".join(pages)
        cache_path.write_text(markdown, encoding="utf-8")
        print(f"  [parser] Fallback extraction: {len(pages)} pages")
        return {
            "paper_id": paper_id,
            "filename": pdf_path,
            "markdown": markdown,
            "tables": [],
            "chunks": [],
            "_doc_result": None,
        }

    except ImportError:
        raise RuntimeError(
            "Docling failed and PyMuPDF is not installed. "
            "Install it with: pip install pymupdf"
        )
    except Exception as e:
        raise RuntimeError(f"Both Docling and PyMuPDF fallback failed: {e}")
