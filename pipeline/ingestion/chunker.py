from typing import Optional

# Tuned for medical papers: smaller chunks improve extraction precision;
# overlap preserves context across boundaries.
_CHUNK_MAX_CHARS = 3000
_MARKDOWN_STEP   = 2500
_MARKDOWN_OVERLAP = 400


def chunk_document(doc_result: dict) -> list[dict]:
    """
    Split a parsed document into chunks with context overlap.
    Attaches caption + surrounding context to figure elements.
    Returns a list of chunk dicts ready for the extractor.
    """
    raw_result = doc_result.get("_doc_result")

    if raw_result is None:
        return _chunk_from_markdown(doc_result["markdown"])

    try:
        elements = list(raw_result.document.iterate_items())
    except Exception:
        return _chunk_from_markdown(doc_result["markdown"])

    chunks = []
    doc = raw_result.document  # needed for export_to_markdown(doc=...)

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
            table_md = _safe_table_export(element, doc)
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

    return merge_chunks(chunks, max_chars=_CHUNK_MAX_CHARS)


def _safe_table_export(element, doc) -> str:
    """Export a table element to markdown, handling the new doc= signature."""
    try:
        return element.export_to_markdown(doc=doc)
    except TypeError:
        # Older docling version without doc argument
        try:
            return element.export_to_markdown()
        except Exception:
            return getattr(element, "text", "[table]")
    except Exception:
        return getattr(element, "text", "[table]")


def _chunk_from_markdown(markdown: str) -> list[dict]:
    """
    Fallback: split raw markdown into overlapping windows.
    step = _MARKDOWN_STEP, overlap = _MARKDOWN_OVERLAP.
    """
    chunks = []
    text = markdown
    i = 0
    while i < len(text):
        chunk_text = text[i: i + _MARKDOWN_STEP]
        chunks.append({"type": "text", "content": chunk_text, "page": None})
        i += _MARKDOWN_STEP - _MARKDOWN_OVERLAP
        if i >= len(text):
            break
    return chunks


def merge_chunks(chunks: list[dict], max_chars: int = _CHUNK_MAX_CHARS) -> list[dict]:
    """
    Merge small adjacent text chunks so each is close to max_chars.
    Tables and figures are always kept as individual chunks.
    When a text buffer overflows, the last _MARKDOWN_OVERLAP chars are
    carried into the next chunk to preserve context at boundaries.
    """
    merged = []
    buffer = ""
    buffer_page: Optional[int] = None

    for chunk in chunks:
        if chunk["type"] in ("table", "figure"):
            if buffer.strip():
                merged.append({"type": "text", "content": buffer.strip(), "page": buffer_page})
                buffer = ""
                buffer_page = None
            merged.append(chunk)
        else:
            content = chunk.get("content", "")
            if len(buffer) + len(content) > max_chars and buffer.strip():
                merged.append({"type": "text", "content": buffer.strip(), "page": buffer_page})
                # carry overlap into next buffer for context continuity
                buffer = buffer[-_MARKDOWN_OVERLAP:] + "\n\n" + content
                buffer_page = chunk.get("page")
            else:
                if buffer_page is None and chunk.get("page") is not None:
                    buffer_page = chunk["page"]
                buffer += "\n\n" + content

    if buffer.strip():
        merged.append({"type": "text", "content": buffer.strip(), "page": buffer_page})

    return merged
