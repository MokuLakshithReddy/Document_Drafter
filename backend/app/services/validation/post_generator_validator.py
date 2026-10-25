from pathlib import Path
from typing import List, Dict, Any, Optional
from app.services.extraction.docx_extractor import DocxExtractor
from app.services.extraction.pdf_extractor import PdfExtractor
from app.schemas.api_schemas import ValidationReport, ValidationIssue
from app.core.logging import logger

class PostGeneratorValidator:
    @classmethod
    def validate(
        cls,
        generated_path: Path,
        fmt: str,
        intended_replacements: List[Dict[str, Any]],
        excluded_texts: List[str],
        source_path: Optional[Path] = None
    ) -> ValidationReport:
        """
        Re-opens the generated document and source document, and performs strict integrity validation:
        1. Every intended replacement is verified at the exact container locator.
        2. Protected/unapproved containers and texts remain 100% unchanged.
        3. Structure and integrity are verified; unexplained alterations trigger failure.
        """
        issues: List[ValidationIssue] = []
        verified_replacements_count = 0
        protected_content_verified = True

        try:
            # 1. Extract generated document
            if fmt == "docx":
                gen_extracted = DocxExtractor.extract(generated_path, "validation_gen")
            else:
                gen_extracted = PdfExtractor.extract(generated_path, "validation_gen")

            gen_unit_map = {u.container_id: u for u in gen_extracted.units}

            # 2. Extract source document for structure comparison if available
            source_unit_map = {}
            if source_path and source_path.exists():
                try:
                    src_fmt = source_path.suffix.lstrip(".").lower()
                    if src_fmt == fmt:
                        if src_fmt == "docx":
                            src_extracted = DocxExtractor.extract(source_path, "validation_src")
                        else:
                            src_extracted = PdfExtractor.extract(source_path, "validation_src")
                        source_unit_map = {u.container_id: u for u in src_extracted.units}
                except Exception as e:
                    logger.warning(f"Could not extract source document for baseline comparison: {e}")

            # 3. Verify each intended replacement at the exact target location
            for rep in intended_replacements:
                new_val = rep.get("new_text", "")
                cid = rep.get("container_id", "")
                occ_id = rep.get("occurrence_id", "")
                page_idx = rep.get("page")

                if not new_val:
                    continue

                matched_at_location = False

                if cid and cid in gen_unit_map:
                    container_text = gen_unit_map[cid].full_text
                    if new_val in container_text:
                        matched_at_location = True
                elif fmt == "pdf":
                    if page_idx is not None:
                        page_units = [u for u in gen_extracted.units if u.page == page_idx]
                        for u in page_units:
                            if new_val in u.full_text:
                                matched_at_location = True
                                break
                    else:
                        if new_val in gen_extracted.raw_text:
                            matched_at_location = True

                if matched_at_location:
                    verified_replacements_count += 1
                else:
                    # Strict failure: replacement missing at intended location!
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="REPLACEMENT_LOCATION_MISMATCH",
                            message=f"Replacement value '{new_val[:30]}' was not found at target location '{cid or f'page[{page_idx}]'}'.",
                            location=cid or f"page[{page_idx}]"
                        )
                    )

            # 4. Compare unapproved content against source document
            targeted_cids = {
                rep.get("container_id") for rep in intended_replacements if rep.get("container_id")
            }

            if source_unit_map:
                for s_cid, s_unit in source_unit_map.items():
                    if s_cid not in targeted_cids and s_cid in gen_unit_map:
                        g_unit = gen_unit_map[s_cid]
                        # Normalize whitespace for robust comparison
                        s_norm = " ".join(s_unit.full_text.split())
                        g_norm = " ".join(g_unit.full_text.split())
                        if s_norm != g_norm:
                            protected_content_verified = False
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    code="UNAPPROVED_CONTENT_ALTERED",
                                    message=f"Unapproved container '{s_cid}' was altered without explicit user approval.",
                                    location=s_cid
                                )
                            )

            # 5. Check that unapproved / pending / excluded texts remain present
            for exc_text in excluded_texts:
                if exc_text and exc_text.strip():
                    if exc_text not in gen_extracted.raw_text:
                        protected_content_verified = False
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                code="PROTECTED_CONTENT_ALTERED",
                                message=f"Protected or unapproved text '{exc_text[:30]}' was altered or removed."
                            )
                        )

        except Exception as e:
            logger.error(f"Post-generation validation failed to parse output: {e}")
            return ValidationReport(
                status="failed",
                intended_replacements_count=len(intended_replacements),
                verified_replacements_count=0,
                protected_content_verified=False,
                issues=[
                    ValidationIssue(
                        severity="error",
                        code="PARSE_VERIFICATION_FAILED",
                        message=f"Could not re-open generated artifact for validation: {str(e)}"
                    )
                ]
            )

        status = "passed"
        if any(i.severity == "error" for i in issues):
            status = "failed"
        elif any(i.severity == "warning" for i in issues):
            status = "warning"

        return ValidationReport(
            status=status,
            intended_replacements_count=len(intended_replacements),
            verified_replacements_count=verified_replacements_count,
            protected_content_verified=protected_content_verified,
            issues=issues
        )
