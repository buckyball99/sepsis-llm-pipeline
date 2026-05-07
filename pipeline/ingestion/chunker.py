from typing import Optional


def chunk_document(doc_result: dict) -> list[dict]:
    """
    Split a parsed document into chunks.
    Attaches caption + surrounding context to figure elements.
    Returns list of chunk dicts ready for the extractor.
    """
    raw_result = doc_result.get("_doc_result")

    # If we only have markdown (from cache), fall back to text-window chunking
    if raw_result is None:
        return _chunk_from_markdown(doc_result["markdown"])

    chunks = []
    try:
        elements = list(raw_result.document.iterate_items())
    except Exception:
        return _chunk_from_markdown(doc_result["markdown"])

    for i, (element, _) in enumerate(elements):
        label = getattr(element, "label", "")

        if label == "picture":
            caption = ""
            context_before = ""
            if i + 1 < len(elements) and getattr(elements[i + 1][0], "label", "") == "caption":
                caption = getattr(elements[i + 1][0], "text", "")
            if i > 0 and getattr(elements[i - 1][0], "label", "") in ("text", "paragraph"):
                context_before = getattr(elements[i - 1][0], "text", "")[-300:]

            chunks.append({
                "type": "figure",
                "content": f"[FIGURE] Caption: {caption}. Surrounding context: {context_before}",
                "page": getattr(element, "page_no", None),
            })

        elif label == "table":
            caption = ""
            if i + 1 < len(elements) and getattr(elements[i + 1][0], "label", "") == "caption":
                caption = getattr(elements[i + 1][0], "text", "")
            try:
                table_md = element.export_to_markdown()
            except Exception:
                table_md = getattr(element, "text", "[table]")
            chunks.append({
                "type": "table",
                "content": table_md,
                "caption": caption,
                "page": getattr(element, "page_no", None),
            })

        elif label in ("text", "paragraph", "section_header"):
            chunks.append({
                "type": "text",
                "content": getattr(element, "text", ""),
                "page": getattr(element, "page_no", None),
            })

    return merge_chunks(chunks, max_chars=6000)


def _chunk_from_markdown(markdown: str) -> list[dict]:
    """Fallback: split raw markdown into ~6000 char windows."""
    chunks = []
    step = 5500
    overlap = 500
    text = markdown
    i = 0
    while i < len(text):
        chunk_text = text[i: i + step]
        chunks.append({"type": "text", "content": chunk_text, "page": None})
        i += step - overlap
    return chunks


def merge_chunks(chunks: list[dict], max_chars: int = 6000) -> list[dict]:
    """
    Merge small adjacent text chunks so each chunk is close to max_chars.
    Tables and figures are always kept as individual chunks.
    """
    merged = []
    buffer = ""
    buffer_pages = []

    for chunk in chunks:
        if chunk["type"] in ("table", "figure"):
            # Flush text buffer first
            if buffer.strip():
                merged.append({"type": "text", "content": buffer.strip(), "page": buffer_pages[0] if buffer_pages else None})
                buffer = ""
                buffer_pages = []
            merged.append(chunk)
        else:
            content = chunk.get("content", "")
            if len(buffer) + len(content) > max_chars and buffer.strip():
                merged.append({"type": "text", "content": buffer.strip(), "page": buffer_pages[0] if buffer_pages else None})
                buffer = content
                buffer_pages = [chunk.get("page")]
            else:
                buffer += "\n\n" + content
                if chunk.get("page") is not None:
                    buffer_pages.append(chunk["page"])

    if buffer.strip():
        merged.append({"type": "text", "content": buffer.strip(), "page": buffer_pages[0] if buffer_pages else None})

    return merged
