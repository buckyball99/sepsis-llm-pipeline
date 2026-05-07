import hashlib
from marker.convert import convert_single_pdf
from marker.models import load_all_models

_models = None

def get_models():
    global _models
    if _models is None:
        _models = load_all_models()
    return _models

def parse_pdf(pdf_path: str) -> dict:
    full_text, images, metadata = convert_single_pdf(pdf_path, get_models())
    paper_id = hashlib.md5(pdf_path.encode()).hexdigest()
    return {
        "paper_id": paper_id,
        "filename": pdf_path,
        "markdown": full_text,
        "chunks": []
    }