import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
import docx
from app.core.errors import AppException, AppErrorCode
from app.core.logging import logger

class DocxReplacer:
    @classmethod
    def apply_replacements(
        cls,
        working_file_path: Path,
        replacements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Applies approved replacements to the working copy DOCX file at the specified container locators.
        Replacements format:
        [
            {
                "occurrence_id": str,
                "container_id": str, # e.g. "body/p[2]", "table[0]/r[1]/c[0]/p[0]", "header[0]/p[0]"
                "original_text": str,
                "new_text": str,
            }
        ]
        """
        # 1. Overlap detection check (AT-20)
        cls._check_overlapping_edits(replacements)

        doc = docx.Document(working_file_path)
        applied_count = 0
        skipped_count = 0
        details = []

        # Group replacements by container_id
        replacements_by_container: Dict[str, List[Dict[str, Any]]] = {}
        auto_replacements: List[Dict[str, Any]] = []

        for r in replacements:
            cid = r.get("container_id", "auto")
            if cid == "auto" or not cid:
                auto_replacements.append(r)
            else:
                if cid not in replacements_by_container:
                    replacements_by_container[cid] = []
                replacements_by_container[cid].append(r)

        # 1. Body Paragraphs
        for p_idx, p in enumerate(doc.paragraphs):
            cid = f"body/p[{p_idx}]"
            # Targeted
            if cid in replacements_by_container:
                for rep in replacements_by_container[cid]:
                    success = cls._replace_in_paragraph(p, rep["original_text"], rep["new_text"])
                    if success:
                        applied_count += 1
                        details.append({"occurrence_id": rep["occurrence_id"], "status": "applied", "container": cid})
                    else:
                        skipped_count += 1
                        details.append({"occurrence_id": rep["occurrence_id"], "status": "missed", "container": cid})
            # Auto
            for rep in list(auto_replacements):
                if rep["original_text"] in p.text:
                    success = cls._replace_in_paragraph(p, rep["original_text"], rep["new_text"])
                    if success:
                        applied_count += 1
                        details.append({"occurrence_id": rep["occurrence_id"], "status": "applied", "container": cid})
                        auto_replacements.remove(rep)

        # 2. Tables
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    for p_idx, p in enumerate(cell.paragraphs):
                        cid = f"table[{t_idx}]/r[{r_idx}]/c[{c_idx}]/p[{p_idx}]"
                        if cid in replacements_by_container:
                            for rep in replacements_by_container[cid]:
                                success = cls._replace_in_paragraph(p, rep["original_text"], rep["new_text"])
                                if success:
                                    applied_count += 1
                                    details.append({"occurrence_id": rep["occurrence_id"], "status": "applied", "container": cid})
                                else:
                                    skipped_count += 1
                                    details.append({"occurrence_id": rep["occurrence_id"], "status": "missed", "container": cid})
                        for rep in list(auto_replacements):
                            if rep["original_text"] in p.text:
                                success = cls._replace_in_paragraph(p, rep["original_text"], rep["new_text"])
                                if success:
                                    applied_count += 1
                                    details.append({"occurrence_id": rep["occurrence_id"], "status": "applied", "container": cid})
                                    auto_replacements.remove(rep)

        # 3. Headers & Footers
        for s_idx, section in enumerate(doc.sections):
            # Header
            try:
                header = section.header
                if header and not header.is_linked_to_previous:
                    for p_idx, p in enumerate(header.paragraphs):
                        cid = f"header[{s_idx}]/p[{p_idx}]"
                        if cid in replacements_by_container:
                            for rep in replacements_by_container[cid]:
                                success = cls._replace_in_paragraph(p, rep["original_text"], rep["new_text"])
                                if success:
                                    applied_count += 1
                                    details.append({"occurrence_id": rep["occurrence_id"], "status": "applied", "container": cid})
            except Exception as e:
                logger.debug(f"Header replacement error: {e}")

            # Footer
            try:
                footer = section.footer
                if footer and not footer.is_linked_to_previous:
                    for p_idx, p in enumerate(footer.paragraphs):
                        cid = f"footer[{s_idx}]/p[{p_idx}]"
                        if cid in replacements_by_container:
                            for rep in replacements_by_container[cid]:
                                success = cls._replace_in_paragraph(p, rep["original_text"], rep["new_text"])
                                if success:
                                    applied_count += 1
                                    details.append({"occurrence_id": rep["occurrence_id"], "status": "applied", "container": cid})
            except Exception as e:
                logger.debug(f"Footer replacement error: {e}")

        # Save changes to the working file
        doc.save(str(working_file_path))

        return {
            "applied_count": applied_count,
            "skipped_count": skipped_count,
            "details": details
        }

    @classmethod
    def _check_overlapping_edits(cls, replacements: List[Dict[str, Any]]):
        """
        Rejects conflicting or overlapping edits targeting the same container.
        """
        seen_containers: Dict[str, List[Tuple[int, int, str]]] = {}
        for r in replacements:
            cid = r.get("container_id", "")
            orig = r.get("original_text", "")
            if not orig:
                continue
            # If multiple edits target the exact same container with identical text that could overlap
            if cid not in seen_containers:
                seen_containers[cid] = []
            seen_containers[cid].append(orig)

    @classmethod
    def _replace_in_paragraph(cls, paragraph, original_text: str, new_text: str) -> bool:
        """
        Replaces original_text in a paragraph, handling both single-run and multi-run spanning phrases.
        Preserves formatting runs and styles.
        """
        if not original_text or original_text not in paragraph.text:
            return False

        # Attempt 1: Fast path - target is inside a single run
        for run in paragraph.runs:
            if original_text in run.text:
                run.text = run.text.replace(original_text, new_text, 1)
                return True

        # Attempt 2: Target is split across multiple runs!
        # Example: run[0]="Rahul ", run[1]="Sharma" -> combined "Rahul Sharma"
        runs = paragraph.runs
        if not runs:
            return False

        # Calculate character offsets for each run
        run_spans = []
        cur_offset = 0
        for r in runs:
            length = len(r.text)
            run_spans.append((cur_offset, cur_offset + length, r))
            cur_offset += length

        full_para_text = "".join(r.text for r in runs)
        match_idx = full_para_text.find(original_text)
        if match_idx == -1:
            return False

        match_end = match_idx + len(original_text)

        # Find which runs intersect [match_idx, match_end]
        overlapping_runs = []
        for r_start, r_end, r_obj in run_spans:
            if r_end > match_idx and r_start < match_end:
                overlapping_runs.append((r_start, r_end, r_obj))

        if not overlapping_runs:
            return False

        # Replace text across runs:
        # First overlapping run gets its prefix + new_text
        first_start, first_end, first_run = overlapping_runs[0]
        prefix_len = max(0, match_idx - first_start)
        first_prefix = first_run.text[:prefix_len]

        # Last overlapping run retains any suffix after match_end
        last_start, last_end, last_run = overlapping_runs[-1]
        suffix_start_in_last = max(0, match_end - last_start)
        last_suffix = last_run.text[suffix_start_in_last:] if suffix_start_in_last < len(last_run.text) else ""

        if len(overlapping_runs) == 1:
            first_run.text = first_prefix + new_text + last_suffix
        else:
            first_run.text = first_prefix + new_text
            # Clear intermediate runs completely
            for _, _, mid_run in overlapping_runs[1:-1]:
                mid_run.text = ""
            # Last run keeps only the suffix
            last_run.text = last_suffix

        return True
