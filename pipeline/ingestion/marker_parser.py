import hashlib
import os
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

# Load models once — expensive, don't repeat
_converter = None

def get_converter():
    global _converter
    if _converter is None:
        _converter = PdfConverter(artifact_dict=create_model_dict())
    return _converter

def parse_pdf(pdf_path: str) -> dict:
    pdf_path = str(pdf_path)
    paper_id = hashlib.md5(pdf_path.encode()).hexdigest()

    cache_path = Path("data/processed") / f"{paper_id}.md"
    os.makedirs("data/processed", exist_ok=True)

    if cache_path.exists():
        print(f"  [parser] Using cached markdown for {os.path.basename(pdf_path)}")
        markdown = cache_path.read_text()
        return {
            "paper_id": paper_id,
            "filename": pdf_path,
            "markdown": markdown,
            "tables": [],
            "chunks": [],
            "_doc_result": None,
        }

    print(f"  [parser] Parsing {os.path.basename(pdf_path)} with Marker...")
    converter = get_converter()
    rendered = converter(pdf_path)
    markdown, _, _ = text_from_rendered(rendered)

    cache_path.write_text(markdown)

    return {
        "paper_id": paper_id,
        "filename": pdf_path,
        "markdown": markdown,
        "tables": [],
        "chunks": [],
        "_doc_result": None,
    }