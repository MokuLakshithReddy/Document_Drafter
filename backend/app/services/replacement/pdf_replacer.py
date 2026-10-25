from pathlib import Path
from typing import List, Dict, Any, Optional
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
        Applies replacements to text-based PDF targeting ONLY the selected occurrence.
        Uses verified page and bounding box information.
        Does NOT redact all matching instances on the page.
        """
        doc = fitz.open(working_file_path)
        applied_count = 0
        skipped_count = 0
        details = []
        warnings = []

        for rep in replacements:
            orig = rep.get("original_text", "")
            new_val = rep.get("new_text", "")
            target_page_idx = rep.get("page")
            target_bbox = rep.get("bbox")
            occ_id = rep.get("occurrence_id", "")

            if not orig:
                continue

            # Determine page range to check
            if target_page_idx is not None and 0 <= target_page_idx < len(doc):
                page_indices = [target_page_idx]
            else:
                page_indices = list(range(len(doc)))

            target_rect = fitz.Rect(target_bbox) if target_bbox and len(target_bbox) == 4 else None
            matched_page = None
            matched_rect = None

            for p_idx in page_indices:
                page = doc[p_idx]
                text_instances = page.search_for(orig)
                if not text_instances:
                    continue

                if target_rect:
                    # Find instance closest to or intersecting target_rect
                    best_match = None
                    best_score = float("inf")
                    for r in text_instances:
                        # Check intersection
                        if r.intersects(target_rect):
                            best_match = r
                            break
                        # Distance between top-left points
                        dist = abs(r.x0 - target_rect.x0) + abs(r.y0 - target_rect.y0)
                        if dist < best_score:
                            best_score = dist
                            best_match = r
                    matched_rect = best_match
                else:
                    matched_rect = text_instances[0]

                if matched_rect:
                    matched_page = page
                    break

            if matched_page and matched_rect:
                # 1. Redact ONLY this single matched occurrence!
                matched_page.add_redact_annot(matched_rect, fill=(1, 1, 1))
                matched_page.apply_redactions()

                # 2. Estimate and adjust font size to prevent overflow
                rect_height = matched_rect.height
                rect_width = matched_rect.width
                font_size = max(7.0, min(13.0, rect_height * 0.8))

                # Check fit
                approx_text_width = len(new_val) * (font_size * 0.52)
                if approx_text_width > rect_width * 1.3:
                    # Downscale font slightly to fit
                    adjusted_font = max(6.0, font_size * (rect_width / approx_text_width))
                    font_size = adjusted_font
                    warnings.append(
                        f"Occurrence {occ_id}: replacement text '{new_val[:20]}' exceeds original width. Scaled font to {font_size:.1f}pt."
                    )

                # 3. Insert replacement text into the specific rectangle
                matched_page.insert_textbox(
                    matched_rect,
                    new_val,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0, 0, 0)
                )

                applied_count += 1
                details.append({
                    "occurrence_id": occ_id,
                    "status": "applied",
                    "page": target_page_idx,
                    "bbox": [matched_rect.x0, matched_rect.y0, matched_rect.x1, matched_rect.y1]
                })
            else:
                skipped_count += 1
                details.append({
                    "occurrence_id": occ_id,
                    "status": "missed",
                    "reason": "Target occurrence bounding box or text not found on page"
                })

        temp_save = working_file_path.with_name(f"temp_{working_file_path.name}")
        doc.save(str(temp_save))
        doc.close()

        import shutil
        shutil.move(str(temp_save), str(working_file_path))

        return {
            "applied_count": applied_count,
            "skipped_count": skipped_count,
            "details": details,
            "warnings": warnings
        }
