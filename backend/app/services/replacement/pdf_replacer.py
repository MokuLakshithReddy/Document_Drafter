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

            # Determine page to check - fail closed if missing or out of range
            if target_page_idx is None or target_page_idx < 0 or target_page_idx >= len(doc):
                raise AppException(
                    code=AppErrorCode.GENERATION_ERROR,
                    message=f"Occurrence {occ_id} for '{orig}' is missing valid target page index ({target_page_idx}). Rejecting ambiguous replacement."
                )

            page = doc[target_page_idx]
            text_instances = page.search_for(orig)
            if not text_instances:
                raise AppException(
                    code=AppErrorCode.GENERATION_ERROR,
                    message=f"Occurrence {occ_id} text '{orig}' not found on target page {target_page_idx}."
                )

            target_rect = fitz.Rect(target_bbox) if target_bbox and len(target_bbox) == 4 else None
            matched_rect = None

            if target_rect:
                # Epsilon padding of 3 points for slight coordinate / rounding variations
                padded_target = fitz.Rect(
                    target_rect.x0 - 3.0,
                    target_rect.y0 - 3.0,
                    target_rect.x1 + 3.0,
                    target_rect.y1 + 3.0
                )
                for r in text_instances:
                    if r.intersects(padded_target):
                        matched_rect = r
                        break

                if not matched_rect:
                    # Never fall back to distant / arbitrary text!
                    raise AppException(
                        code=AppErrorCode.GENERATION_ERROR,
                        message=f"Occurrence {occ_id} for '{orig}' does not intersect target bounding box {target_bbox} on page {target_page_idx}. Rejecting unverified replacement."
                    )
            else:
                # Bounding box was not provided
                if len(text_instances) > 1:
                    raise AppException(
                        code=AppErrorCode.GENERATION_ERROR,
                        message=f"Occurrence {occ_id} for '{orig}' is ambiguous ({len(text_instances)} instances on page {target_page_idx} without bounding box). Rejecting ambiguous replacement."
                    )
                matched_rect = text_instances[0]

            # 1. Extract exact typography from the matched span before redaction
            text_dict = page.get_text("dict", clip=matched_rect)
            detected_size = None
            detected_font = "helv"
            detected_color = (0, 0, 0)

            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            detected_size = span.get("size")
                            font_name = span.get("font", "").lower()
                            flags = span.get("flags", 0)
                            color_int = span.get("color", 0)

                            is_bold = bool(flags & 4) or ("bold" in font_name) or ("black" in font_name)
                            is_italic = bool(flags & 2) or ("italic" in font_name) or ("oblique" in font_name)

                            if any(k in font_name for k in ["times", "roman", "serif"]):
                                if is_bold and is_italic:
                                    detected_font = "tibi"
                                elif is_bold:
                                    detected_font = "tibo"
                                elif is_italic:
                                    detected_font = "tiit"
                                else:
                                    detected_font = "tiro"
                            elif any(k in font_name for k in ["courier", "mono"]):
                                if is_bold and is_italic:
                                    detected_font = "cobi"
                                elif is_bold:
                                    detected_font = "cobo"
                                elif is_italic:
                                    detected_font = "coit"
                                else:
                                    detected_font = "cour"
                            else: # Helvetica / Arial / Sans default
                                if is_bold and is_italic:
                                    detected_font = "hebi"
                                elif is_bold:
                                    detected_font = "hebo"
                                elif is_italic:
                                    detected_font = "heit"
                                else:
                                    detected_font = "helv"

                            if color_int:
                                detected_color = fitz.sRGB_to_rgb(color_int)
                            break
                    if detected_size:
                        break
                if detected_size:
                    break

            # 2. Redact ONLY this single verified matched occurrence
            page.add_redact_annot(matched_rect, fill=(1, 1, 1))
            page.apply_redactions()

            # 3. Use detected font size or bound-checked estimate
            font_size = detected_size if detected_size else max(7.0, min(13.0, matched_rect.height * 0.8))

            approx_text_width = len(new_val) * (font_size * 0.52)
            if approx_text_width > matched_rect.width * 1.3:
                adjusted_font = max(5.5, font_size * (matched_rect.width / approx_text_width))
                font_size = adjusted_font
                warnings.append(
                    f"Occurrence {occ_id}: replacement text scaled to {font_size:.1f}pt to preserve bounding layout."
                )

            # 4. Insert replacement text with verified typography
            page.insert_textbox(
                matched_rect,
                new_val,
                fontsize=font_size,
                fontname=detected_font,
                color=detected_color
            )

            applied_count += 1
            details.append({
                "occurrence_id": occ_id,
                "status": "applied",
                "page": target_page_idx,
                "bbox": [matched_rect.x0, matched_rect.y0, matched_rect.x1, matched_rect.y1]
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
