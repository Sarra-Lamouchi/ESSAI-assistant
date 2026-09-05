import pdfplumber
import fitz  # PyMuPDF
from docling.document_converter import DocumentConverter
import json
import os
import re
import unicodedata
from datetime import date

# Initialisation unique de Docling 
_docling_converter = None
def get_docling_converter():
    global _docling_converter
    if _docling_converter is None:
        _docling_converter = DocumentConverter()
    return _docling_converter


def sanitize_filename(filename):
    """Retire les accents et caractères spéciaux d'un nom de fichier, garde l'extension"""
    name, ext = os.path.splitext(filename)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\-]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name + ext


def extract_with_pdfplumber(pdf_path):
    result = {"filename": os.path.basename(pdf_path), "extractor": "pdfplumber", "pages": []}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            tables = page.extract_tables()
            result["pages"].append({
                "page_number": i + 1,
                "text": text,
                "tables": tables,
                "char_count": len(text)
            })
    return result


def extract_with_pymupdf(pdf_path):
    result = {"filename": os.path.basename(pdf_path), "extractor": "pymupdf", "pages": []}
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        text = page.get_text("text")
        result["pages"].append({
            "page_number": i + 1,
            "text": text,
            "tables": [],
            "char_count": len(text)
        })
    return result


def extract_with_docling(pdf_path):
    """Docling gère le PDF directement, layout + OCR intégré, pas besoin de Poppler"""
    converter = get_docling_converter()
    result_obj = converter.convert(pdf_path)
    doc = result_obj.document

    result = {"filename": os.path.basename(pdf_path), "extractor": "docling", "pages": []}

    pages_text = {}
    for item, _ in doc.iterate_items():
        page_no = getattr(item.prov[0], "page_no", 1) if item.prov else 1
        text = getattr(item, "text", "") or ""
        pages_text.setdefault(page_no, []).append(text)

    tables_by_page = {}
    for table in doc.tables:
        page_no = table.prov[0].page_no if table.prov else 1
        tables_by_page.setdefault(page_no, []).append(table.export_to_dataframe().values.tolist())

    for page_no in sorted(pages_text.keys()) or [1]:
        text = "\n".join(pages_text.get(page_no, []))
        result["pages"].append({
            "page_number": page_no,
            "text": text,
            "tables": tables_by_page.get(page_no, []),
            "char_count": len(text)
        })

    return result


EXTRACTORS = {
    "pdfplumber": extract_with_pdfplumber,
    "pymupdf": extract_with_pymupdf,
    "docling": extract_with_docling,
}


def run_extraction(pdf_path, extractor_name, output_base="../data/processed/extracted_text"):
    extractor_fn = EXTRACTORS[extractor_name]
    data = extractor_fn(pdf_path)
    data["extraction_date"] = str(date.today())

    output_folder = os.path.join(output_base, extractor_name)
    os.makedirs(output_folder, exist_ok=True)
    output_path = os.path.join(output_folder, data["filename"].replace(".pdf", ".json"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data, output_path