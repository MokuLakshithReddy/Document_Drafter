import logging
import sys
from app.core.config import settings

def setup_logging():
    logger = logging.getLogger("document_reuse")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

logger = setup_logging()

def log_event(event_type: str, resource_id: str, details: str = ""):
    # Strictly avoid logging raw document texts or values
    clean_details = details[:120] if details else ""
    logger.info(f"AUDIT: event={event_type} resource_id={resource_id} {clean_details}")
