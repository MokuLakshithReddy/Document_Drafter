import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    format = Column(String, nullable=False) # docx, pdf
    sha256 = Column(String, nullable=False, index=True)
    storage_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    status = Column(String, default="uploaded") # uploaded, analyzing, analyzed, error
    page_count = Column(Integer, default=1)
    error_message = Column(Text, nullable=True)

    templates = relationship("Template", back_populates="source_document", cascade="all, delete-orphan")

class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    source_document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1)
    status = Column(String, default="active") # active, archived
    source_checksum = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    source_document = relationship("Document", back_populates="templates")
    variables = relationship("TemplateVariable", back_populates="template", cascade="all, delete-orphan")
    generation_jobs = relationship("GenerationJob", back_populates="template", cascade="all, delete-orphan")

class TemplateVariable(Base):
    __tablename__ = "template_variables"

    id = Column(String, primary_key=True, default=generate_uuid)
    template_id = Column(String, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String, nullable=True)
    key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    type = Column(String, default="custom") # person_name, organization, date, address, money, phone, email, identifier, role, location, custom
    required = Column(Boolean, default=True)
    status = Column(String, default="approved") # approved, excluded
    default_value = Column(String, nullable=True)
    description = Column(String, nullable=True)
    confidence = Column(String, nullable=True)

    template = relationship("Template", back_populates="variables")
    occurrences = relationship("VariableOccurrence", back_populates="variable", cascade="all, delete-orphan")

class VariableOccurrence(Base):
    __tablename__ = "variable_occurrences"

    id = Column(String, primary_key=True, default=generate_uuid)
    variable_id = Column(String, ForeignKey("template_variables.id", ondelete="CASCADE"), nullable=False)
    source_locator = Column(JSON, nullable=False) # structured locator details
    original_text = Column(String, nullable=False)
    status = Column(String, default="active") # active, excluded

    variable = relationship("TemplateVariable", back_populates="occurrences")

class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    template_id = Column(String, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    template_version = Column(Integer, nullable=False)
    status = Column(String, default="pending") # pending, processing, completed, failed
    created_at = Column(DateTime, default=utc_now)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    validation_report = Column(JSON, nullable=True)

    template = relationship("Template", back_populates="generation_jobs")
    values = relationship("GenerationValue", back_populates="job", cascade="all, delete-orphan")
    generated_document = relationship("GeneratedDocument", uselist=False, back_populates="job", cascade="all, delete-orphan")

class GenerationValue(Base):
    __tablename__ = "generation_values"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    variable_id = Column(String, nullable=False)
    variable_key = Column(String, nullable=False)
    value = Column(String, nullable=False)
    approved_at = Column(DateTime, default=utc_now)

    job = relationship("GenerationJob", back_populates="values")

class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    format = Column(String, nullable=False) # docx, pdf
    storage_path = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    validation_status = Column(String, default="passed") # passed, warning, failed
    created_at = Column(DateTime, default=utc_now)

    job = relationship("GenerationJob", back_populates="generated_document")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    event_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=utc_now)
    metadata_json = Column(JSON, nullable=True)
