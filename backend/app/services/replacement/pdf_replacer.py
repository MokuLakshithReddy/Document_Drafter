from pathlib import Path
from typing import List, Dict, Any
import pymupdf as fitz # PyMuPDF
from app.core.logging import logger

class PdfReplacer:
    @classmethod
    def apply_replacements(
        cls,
        working_file_path: Path,
        replacements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Applies replacements to text-based PDF using redaction and re-insertion of text at target bounding boxes.
        Replacements format:
        [
            {
                "occurrence_id": str,
                "container_id": str, # e.g. "page[0]/block[1]"
                "original_text": str,
                "new_text": str,
                "bbox": [x0, y0, x1, y1], # optional
                "page": int # optional
            }
        ]
        """
        doc = fitz.open(working_file_path)
        applied_count = 0
        skipped_count = 0
        details = []

        for rep in replacements:
            orig = rep.get("original_text", "")
            new_val = rep.get("new_text", "")
            target_page_idx = rep.get("page")

            if not orig:
                continue

            replaced_in_doc = False
            # If target page is specified, look there first; else check all pages
            page_indices = [target_page_idx] if target_page_idx is not None and 0 <= target_page_idx < len(doc) else range(len(doc))

            for p_idx in page_indices:
                page = doc[p_idx]
                # Search for original text instances on the page
                text_instances = page.search_for(orig)
                if text_instances:
                    # Apply redaction annotation over the text rectangle
                    for rect in text_instances:
                        page.add_redact_annot(rect, fill=(1, 1, 1)) # white out original
                    page.apply_redactions()

                    # Insert new text inside the primary rect
                    primary_rect = text_instances[0]
                    # Estimate font size based on rect height
                    font_size = max(8.0, min(14.0, primary_rect.height * 0.8))
                    page.insert_textbox(
                        primary_rect,
                        new_val,
                        fontsize=font_size,
                        fontname="helv",
                        color=(0, 0, 0)
                    )
                    replaced_in_doc = True
                    break

            if replaced_in_doc:
                applied_count += 1
                details.append({"occurrence_id": rep.get("occurrence_id"), "status": "applied"})
            else:
                skipped_count += 1
                details.append({"occurrence_id": rep.get("occurrence_id"), "status": "missed"})

        temp_save = working_file_path.with_name(f"temp_{working_file_path.name}")
        doc.save(str(temp_save))
        doc.close()

        import shutil
        shutil.move(str(temp_save), str(working_file_path))

        return {
            "applied_count": applied_count,
            "skipped_count": skipped_count,
            "details": details
        }
