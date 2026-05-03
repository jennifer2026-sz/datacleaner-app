"""PDF processor using PyMuPDF (fitz)."""

from pathlib import Path


def process_pdf(filepath: str | Path) -> str:
    """Extract text from a PDF file.

    Handles both native text PDFs and scanned/image-based PDFs
    (limited OCR support via PyMuPDF's built-in text extraction).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(filepath))
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            pages.append(f"--- Page {page_num + 1} ---\n{text}")
        else:
            # Try OCR-like extraction for image-based pages
            blocks = page.get_text("blocks")
            block_texts = [b[4] for b in blocks if b[6] == 0 and b[4].strip()]
            if block_texts:
                pages.append(f"--- Page {page_num + 1} ---\n" + "\n".join(block_texts))

    doc.close()
    return "\n\n".join(pages)


def get_pdf_page_count(filepath: str | Path) -> int:
    """Return the number of pages in a PDF."""
    import fitz
    doc = fitz.open(str(filepath))
    count = len(doc)
    doc.close()
    return count
