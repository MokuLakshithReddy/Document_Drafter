import os
import shutil
import hashlib
import uuid
import zipfile
from pathlib import Path
from typing import Tuple
from app.core.config import settings
from app.core.errors import AppException, AppErrorCode
from app.core.logging import logger

class StorageManager:
    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def validate_file_security(temp_path: Path, filename: str) -> Tuple[str, int]:
        """
        Validates file signature, size, ZIP bomb safety, macro-rejection.
        Returns (format, page_count_hint).
        """
        file_size = temp_path.stat().st_size
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise AppException(
                code=AppErrorCode.FILE_TOO_LARGE,
                message=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
                details={"size_bytes": file_size, "max_bytes": max_bytes}
            )

        with open(temp_path, "rb") as f:
            header = f.read(1024)

        # Check for PDF (%PDF- can appear anywhere within the first 1024 bytes)
        is_pdf = b"%PDF-" in header
        if not is_pdf and filename.lower().endswith(".pdf"):
            import pymupdf as fitz
            try:
                test_doc = fitz.open(temp_path)
                is_pdf = len(test_doc) > 0
                test_doc.close()
            except Exception:
                is_pdf = False

        if is_pdf:
            import pymupdf as fitz
            try:
                doc = fitz.open(temp_path)
                page_count = len(doc)
                doc.close()
            except Exception as e:
                raise AppException(
                    code=AppErrorCode.UNSUPPORTED_FORMAT,
                    message=f"Corrupt or malformed PDF file: {str(e)}"
                )
            if page_count > settings.MAX_PAGE_LIMIT:
                raise AppException(
                    code=AppErrorCode.PAGE_LIMIT_EXCEEDED,
                    message=f"PDF exceeds page limit ({page_count} > {settings.MAX_PAGE_LIMIT})",
                    details={"page_count": page_count, "limit": settings.MAX_PAGE_LIMIT}
                )
            return "pdf", page_count

        # Check for DOCX (ZIP archive: PK\x03\x04 or is_zipfile)
        if header.startswith(b"PK\x03\x04") or zipfile.is_zipfile(temp_path):
            try:
                with zipfile.ZipFile(temp_path, 'r') as z:
                    # Defense against ZIP bombs: check uncompressed size & compression ratio
                    total_uncompressed = 0
                    namelist = z.namelist()

                    # Check for DOCX core files
                    if "[Content_Types].xml" not in namelist or not any(n.startswith("word/") for n in namelist):
                        raise AppException(
                            code=AppErrorCode.UNSUPPORTED_FORMAT,
                            message="Uploaded ZIP archive is not a valid Microsoft Word (.docx) document"
                        )

                    # Reject dangerous macro files
                    if any("vbaProject.bin" in n or n.endswith(".vba") for n in namelist):
                        raise AppException(
                            code=AppErrorCode.DANGEROUS_CONTENT,
                            message="Macro-enabled documents (.docm / VBA scripts) are rejected for security"
                        )

                    for info in z.infolist():
                        total_uncompressed += info.file_size
                        if info.compress_size > 0:
                            ratio = info.file_size / info.compress_size
                            if ratio > 100:
                                raise AppException(
                                    code=AppErrorCode.INVALID_ARCHIVE,
                                    message="Potential ZIP bomb detected (extreme compression ratio)"
                                )
                    
                    if total_uncompressed > 100 * 1024 * 1024: # 100MB safety ceiling
                        raise AppException(
                            code=AppErrorCode.INVALID_ARCHIVE,
                            message="Uncompressed archive content exceeds safety limits (100MB)"
                        )

            except zipfile.BadZipFile:
                raise AppException(
                    code=AppErrorCode.INVALID_ARCHIVE,
                    message="Corrupt or malformed ZIP archive"
                )
            
            return "docx", 1

        raise AppException(
            code=AppErrorCode.UNSUPPORTED_FORMAT,
            message="Unsupported file format. Please upload a valid DOCX or text-based PDF file."
        )

    @classmethod
    def save_upload(cls, original_filename: str, source_bytes: bytes) -> Tuple[str, str, str, Path, int]:
        """
        Saves uploaded file into quarantine/temp first, validates, then commits to originals/.
        Returns (doc_id, format, sha256, stored_path, page_count).
        """
        doc_id = str(uuid.uuid4())
        safe_ext = Path(original_filename).suffix.lower()
        if safe_ext not in [".docx", ".pdf"]:
            # Check by content, but fallback default ext
            safe_ext = ".docx"

        temp_file = settings.temp_path / f"temp_{doc_id}{safe_ext}"
        try:
            with open(temp_file, "wb") as f:
                f.write(source_bytes)

            fmt, page_count = cls.validate_file_security(temp_file, original_filename)
            file_hash = cls.compute_sha256(temp_file)

            final_filename = f"{doc_id}.{fmt}"
            final_path = settings.originals_path / final_filename

            # Move from temp to originals
            shutil.move(str(temp_file), str(final_path))
            return doc_id, fmt, file_hash, final_path, page_count

        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    @classmethod
    def create_working_copy(cls, original_path: Path, prefix: str = "work") -> Path:
        """
        Creates a copy of the original file in the working directory to preserve the original.
        """
        if not original_path.exists():
            raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Original file not found on disk")
        
        copy_id = f"{prefix}_{uuid.uuid4()}{original_path.suffix}"
        target_path = settings.working_path / copy_id
        shutil.copy2(str(original_path), str(target_path))
        return target_path

    @classmethod
    def delete_document_files(cls, original_path_str: str):
        """
        Safely deletes original file and any matching working or generated artifacts.
        """
        try:
            p = Path(original_path_str).resolve()
            if p.exists() and p.is_file():
                # Defend against deleting files outside storage_dir
                base_dir = settings.base_storage_path.resolve()
                if base_dir in p.parents or p.parent == base_dir:
                    p.unlink()
                    logger.info(f"Deleted file: {p}")
        except Exception as e:
            logger.warning(f"Error deleting file {original_path_str}: {e}")
