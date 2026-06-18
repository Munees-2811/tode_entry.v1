import os
import tempfile
from PIL import Image


def pdf_to_images(pdf_path, dpi=300):
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    images = []
    temp_dir = tempfile.mkdtemp(prefix="tode_pdf_")

    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)

        img_path = os.path.join(temp_dir, f"page_{page_num + 1}.png")
        pix.save(img_path)
        images.append({"page": page_num + 1, "path": img_path, "width": pix.width, "height": pix.height})

    doc.close()
    return images


def get_pdf_page_count(pdf_path):
    try:
        import fitz
    except ImportError:
        return 0

    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def extract_pdf_text_native(pdf_path, page_num=None):
    try:
        import fitz
    except ImportError:
        return ""

    doc = fitz.open(pdf_path)
    texts = []

    if page_num is not None:
        if 0 <= page_num < len(doc):
            texts.append(doc[page_num].get_text())
    else:
        for page in doc:
            texts.append(page.get_text())

    doc.close()
    return "\n\n".join(texts).strip()
