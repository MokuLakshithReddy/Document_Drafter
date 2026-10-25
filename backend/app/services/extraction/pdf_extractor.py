from pathlib import Path
from typing import List
import pymupdf as fitz # PyMuPDF
from app.services.extraction.models import ExtractedDocument, ExtractedUnit
from app.core.logging import logger

class PdfExtractor:
    @staticmethod
    def extract(file_path: Path, document_id: str) -> ExtractedDocument:
        doc = fitz.open(file_path)
        units: List[ExtractedUnit] = []
        raw_lines: List[str] = []

        total_text_chars = 0
        has_images = False
        is_scanned = False
        scan_warning = None

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            # Check for image content
            image_list = page.get_images()
            if image_list:
                has_images = True

            # Extract text blocks with bounding boxes
            # page.get_text("blocks") returns list of (x0, y0, x1, y1, "text", block_no, block_type)
            blocks = page.get_text("blocks")
            for b_idx, block in enumerate(blocks):
                # block_type 0 = text, 1 = image
                if len(block) >= 5 and block[6] == 0 if len(block) > 6 else True:
                    text = block[4].strip()
                    if text:
                        total_text_chars += len(text)
                        bbox = [round(block[0], 2), round(block[1], 2), round(block[2], 2), round(block[3], 2)]
                        unit = ExtractedUnit(
                            container_id=f"page[{page_idx}]/block[{b_idx}]",
                            kind="pdf_block",
                            full_text=text,
                            page=page_idx,
                            bbox=bbox
                        )
                        units.append(unit)
                        raw_lines.append(text)

        doc.close()

        # Check if scanned document (image-heavy with little/no text)
        if len(units) == 0 or (has_images and total_text_chars < 50):
            is_scanned = True
            scan_warning = "Document appears to be a scanned image or contains no selectable text. OCR is not supported in MVP."

        raw_text = "\n".join(raw_lines)
        return ExtractedDocument(
            document_id=document_id,
            format="pdf",
            units=units,
            raw_text=raw_text,
            total_paragraphs=len(units),
            total_tables=0,
            has_headers_footers=False,
            is_scanned=is_scanned,
            scan_warning=scan_warning
        )
