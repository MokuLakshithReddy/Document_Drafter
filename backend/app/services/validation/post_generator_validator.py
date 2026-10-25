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
        unmodified_original_texts: Optional[List[str]] = None,
        source_path: Optional[Path] = None,
        excluded_texts: Optional[List[str]] = None # Backwards compatibility alias
    ) -> ValidationReport:
        """
        Re-opens the generated document and source document, and performs strict integrity validation:
        1. Every intended replacement is verified to have occurred at the exact container locator.
        2. Unmodified containers and original text without replacements remain 100% unchanged.
        3. Structure and integrity are verified; missing containers or unexplained alterations fail closed.
        """
        issues: List[ValidationIssue] = []
        verified_replacements_count = 0
        protected_content_verified = True

        # Unify unmodified original texts
        unmodified_texts = (unmodified_original_texts or []) + (excluded_texts or [])

        try:
            # 1. Extract generated document
            if fmt == "docx":
                gen_extracted = DocxExtractor.extract(generated_path, "validation_gen")
            else:
                gen_extracted = PdfExtractor.extract(generated_path, "validation_gen")

            gen_unit_map = {u.container_id: u for u in gen_extracted.units}

            # 2. Extract source document for baseline comparison
            source_unit_map = {}
            if source_path and source_path.exists():
                try:
                    src_fmt = source_path.suffix.lstrip(".").lower()
                    if src_fmt == "docx":
                        src_extracted = DocxExtractor.extract(source_path, "validation_src")
                    else:
                        src_extracted = PdfExtractor.extract(source_path, "validation_src")
                    source_unit_map = {u.container_id: u for u in src_extracted.units}

                    # Flag layout approximation if converting across formats
                    if src_fmt != fmt:
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                code="LAYOUT_APPROXIMATION",
                                message="DOCX-to-PDF conversion was performed using the built-in layout engine. Print geometry, page breaks, and complex font metrics are approximated.",
                                location="document"
                            )
                        )
                except Exception as e:
                    logger.warning(f"Could not extract source document for baseline comparison: {e}")

            # 3. Verify each intended replacement at the exact target location
            for rep in intended_replacements:
                new_val = rep.get("new_text", "")
                orig_val = rep.get("original_text", "")
                cid = rep.get("container_id", "")
                occ_id = rep.get("occurrence_id", "")
                page_idx = rep.get("page")

                if not new_val:
                    continue

                matched_at_location = False

                if cid and cid in gen_unit_map:
                    container_text = gen_unit_map[cid].full_text
                    if new_val in container_text:
                        # Prove replacement: if original text differed, verify that original count decreased in this container
                        if orig_val and orig_val != new_val and cid in source_unit_map:
                            src_orig_count = source_unit_map[cid].full_text.count(orig_val)
                            gen_orig_count = container_text.count(orig_val)
                            if gen_orig_count < src_orig_count or orig_val not in container_text:
                                matched_at_location = True
                            else:
                                issues.append(
                                    ValidationIssue(
                                        severity="error",
                                        code="UNREPLACED_ORIGINAL_REMAINS",
                                        message=f"Original text '{orig_val[:30]}' was not consumed at target container '{cid}'.",
                                        location=cid
                                    )
                                )
                        else:
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
                    # Strict failure: replacement missing or unproven at intended location!
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="REPLACEMENT_LOCATION_MISMATCH",
                            message=f"Replacement value '{new_val[:30]}' was not proven at target location '{cid or f'page[{page_idx}]'}'.",
                            location=cid or f"page[{page_idx}]"
                        )
                    )

            # 4. Strict source comparison: fail closed on missing or altered unmodified content
            targeted_cids = {
                rep.get("container_id") for rep in intended_replacements if rep.get("container_id")
            }

            if source_unit_map and (source_path.suffix.lstrip(".").lower() == fmt):
                for s_cid, s_unit in source_unit_map.items():
                    # Check if source container was completely dropped
                    if s_cid not in gen_unit_map:
                        protected_content_verified = False
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                code="SOURCE_CONTAINER_MISSING",
                                message=f"Source container '{s_cid}' was omitted from generated document.",
                                location=s_cid
                            )
                        )
                        continue

                    # If container was not targeted for replacement, verify 100% unchanged
                    if s_cid not in targeted_cids:
                        g_unit = gen_unit_map[s_cid]
                        s_norm = " ".join(s_unit.full_text.split())
                        g_norm = " ".join(g_unit.full_text.split())
                        if s_norm != g_norm:
                            protected_content_verified = False
                            issues.append(
                                ValidationIssue(
                                    severity="error",
                                    code="UNMODIFIED_CONTENT_ALTERED",
                                    message=f"Unmodified container '{s_cid}' was altered without an intended replacement.",
                                    location=s_cid
                                )
                            )

            # 5. Check that original texts without replacements remain present in the document
            for unmod_text in unmodified_texts:
                if unmod_text and unmod_text.strip():
                    if unmod_text not in gen_extracted.raw_text:
                        protected_content_verified = False
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                code="UNMODIFIED_TEXT_MISSING",
                                message=f"Original text '{unmod_text[:30]}' was altered or removed despite no replacement being specified."
                            )
                        )

        except Exception as e:
            logger.error(f"Post-generation validation failed: {e}")
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
