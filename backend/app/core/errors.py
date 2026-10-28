from fastapi import HTTPException, status

class AppErrorCode:
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    INVALID_VALUE = "INVALID_VALUE"
    AMBIGUOUS_OCCURRENCE = "AMBIGUOUS_OCCURRENCE"
    GENERATION_VALIDATION_FAILED = "GENERATION_VALIDATION_FAILED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    INVALID_ARCHIVE = "INVALID_ARCHIVE"
    DANGEROUS_CONTENT = "DANGEROUS_CONTENT"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    OVERLAPPING_EDIT = "OVERLAPPING_EDIT"
    AI_PROVIDER_ERROR = "AI_PROVIDER_ERROR"
    SCANNED_PDF_NO_TEXT = "SCANNED_PDF_NO_TEXT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

class AppException(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "details": details or {}
            }
        )
