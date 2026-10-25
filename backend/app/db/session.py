from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations():
    """Ensure newly added columns exist in existing SQLite tables."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        # Check documents.analysis_json
        if "documents" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("documents")]
            if "analysis_json" not in columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN analysis_json JSON"))

        # Check generation_jobs.output_format
        if "generation_jobs" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("generation_jobs")]
            if "output_format" not in columns:
                conn.execute(text("ALTER TABLE generation_jobs ADD COLUMN output_format VARCHAR DEFAULT 'docx'"))

