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
        # Check documents.analysis_json and documents.owner_id
        if "documents" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("documents")]
            if "analysis_json" not in columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN analysis_json JSON"))
            if "owner_id" not in columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN owner_id VARCHAR DEFAULT 'default'"))

        # Check templates.owner_id
        if "templates" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("templates")]
            if "owner_id" not in columns:
                conn.execute(text("ALTER TABLE templates ADD COLUMN owner_id VARCHAR DEFAULT 'default'"))

        # Check generation_jobs.output_format and generation_jobs.owner_id
        if "generation_jobs" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("generation_jobs")]
            if "output_format" not in columns:
                conn.execute(text("ALTER TABLE generation_jobs ADD COLUMN output_format VARCHAR DEFAULT 'docx'"))
            if "owner_id" not in columns:
                conn.execute(text("ALTER TABLE generation_jobs ADD COLUMN owner_id VARCHAR DEFAULT 'default'"))

# Run migrations on import to guarantee all columns exist across all test & runtime paths
try:
    Base.metadata.create_all(bind=engine)
    run_migrations()
except Exception:
    pass


