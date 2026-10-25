from pathlib import Path
from typing import List, Dict, Any, Tuple
from app.services.extraction.docx_extractor import DocxExtractor
from app.services.extraction.pdf_extractor import PdfExtractor
from app.schemas.api_schemas import ValidationReport, ValidationIssue

class PostGeneratorValidator:
    @classmethod
    def validate(
        cls,
        generated_path: Path,
        fmt: str,
        intended_replacements: List[Dict[str, Any]],
        excluded_texts: List[str]
    ) -> ValidationReport:
        """
        Re-opens the generated document, extracts its content, and performs strict integrity validation:
        1. Intended replacements are present.
        2. Excluded original texts were NOT modified or replaced by mistake.
        3. Document is readable and not corrupt.
        """
        issues: List[ValidationIssue] = []
        verified_replacements_count = 0
        protected_content_verified = True

        try:
            # Reopen and re-extract
            if fmt == "docx":
                extracted = DocxExtractor.extract(generated_path, "validation_check")
            else:
                extracted = PdfExtractor.extract(generated_path, "validation_check")

            all_generated_text = extracted.raw_text

            # 1. Check intended replacements
            for rep in intended_replacements:
                new_val = rep.get("new_text", "")
                orig_val = rep.get("original_text", "")
                occ_id = rep.get("occurrence_id", "")
                container_id = rep.get("container_id", "")

                if not new_val:
                    continue

                if new_val in all_generated_text:
                    verified_replacements_count += 1
                else:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            code="REPLACEMENT_NOT_VERIFIED",
                            message=f"Replacement value '{new_val[:30]}' was not detected in generated output.",
                            location=container_id
                        )
                    )

            # 2. Check excluded/protected texts remain intact
            for exc_text in excluded_texts:
                if exc_text and exc_text.strip():
                    if exc_text not in all_generated_text:
                        protected_content_verified = False
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                code="PROTECTED_CONTENT_ALTERED",
                                message=f"Protected text '{exc_text[:30]}' was unexpectedly removed or modified."
                            )
                        )

        except Exception as e:
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

        # Determine overall status
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
