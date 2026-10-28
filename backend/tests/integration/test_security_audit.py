import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import Settings, settings
from app.db.session import Base, get_db

SEC_TEST_DB_URL = "sqlite:///./test_security.db"
sec_test_engine = create_engine(SEC_TEST_DB_URL, connect_args={"check_same_thread": False})
SecTestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sec_test_engine)

def override_sec_get_db():
    db = SecTestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="module", autouse=True)
def setup_sec_test_db():
    app.dependency_overrides[get_db] = override_sec_get_db
    Base.metadata.drop_all(bind=sec_test_engine)
    Base.metadata.create_all(bind=sec_test_engine)
    yield
    Base.metadata.drop_all(bind=sec_test_engine)
    app.dependency_overrides.pop(get_db, None)
    if Path("./test_security.db").exists():
        try:
            Path("./test_security.db").unlink()
        except Exception:
            pass


def test_cors_strict_allowlist_rejects_arbitrary_origins():
    """Verify that arbitrary / untrusted origins do not receive CORS allow headers."""
    with TestClient(app) as client:
        # Preflight from malicious origin
        res = client.options(
            "/api/v1/documents",
            headers={
                "Origin": "http://evil-attacker.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # The response must NOT reflect the malicious origin
        assert res.headers.get("access-control-allow-origin") != "http://evil-attacker.com"

        # Preflight from trusted allowlisted origin
        res_trusted = client.options(
            "/api/v1/documents",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert res_trusted.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_production_secret_key_validation():
    """Verify that insecure default secret keys are strictly rejected in production."""
    # Attempting to run in production with default local SECRET_KEY must fail
    with pytest.raises(ValueError, match="CRITICAL SECURITY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="local-secret-key-antigravity",
            STORAGE_DIR="./storage",
        )

    # Short secret key must fail in production
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="too-short-secret-key",
            STORAGE_DIR="./storage",
        )

    # In production, if REQUIRE_AUTH is true, API_KEY must be provided
    with pytest.raises(ValueError, match="API_KEY is missing or too short"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secret-production-random-key-1234567890",
            REQUIRE_AUTH=True,
            API_KEY="",
            STORAGE_DIR="./storage",
        )

    # Valid production settings must succeed
    valid_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-production-random-key-1234567890",
        REQUIRE_AUTH=True,
        API_KEY="prod-api-key-abcdef",
        STORAGE_DIR="./storage",
    )
    assert valid_prod.ENVIRONMENT == "production"
    assert valid_prod.API_KEY == "prod-api-key-abcdef"


def test_api_key_authentication_enforcement(tmp_path):
    """Verify 401 Unauthorized when REQUIRE_AUTH is enabled and no or invalid key is supplied."""
    app_settings = settings

    original_require_auth = app_settings.REQUIRE_AUTH
    original_api_key = app_settings.API_KEY
    try:
        app_settings.REQUIRE_AUTH = True
        app_settings.API_KEY = "test-secret-api-key-123"

        with TestClient(app) as client:
            # 1. Unauthenticated request -> 401
            res = client.get("/api/v1/documents/non-existent-id")
            assert res.status_code == 401
            assert "missing API key" in res.text

            # 2. Invalid API key -> 401
            res = client.get(
                "/api/v1/documents/non-existent-id",
                headers={"X-API-Key": "wrong-key"}
            )
            assert res.status_code == 401

            # 3. Valid API key via X-API-Key -> Auth passed (404 for non-existent document, not 401)
            res = client.get(
                "/api/v1/documents/non-existent-id",
                headers={"X-API-Key": "test-secret-api-key-123"}
            )
            assert res.status_code == 404

            # 4. Valid API key via Authorization: Bearer
            res = client.get(
                "/api/v1/documents/non-existent-id",
                headers={"Authorization": "Bearer test-secret-api-key-123"}
            )
            assert res.status_code == 404

            # 5. Settings endpoint protected by auth
            res_settings = client.get("/api/v1/settings")
            assert res_settings.status_code == 401

            res_settings_authed = client.get(
                "/api/v1/settings",
                headers={"X-API-Key": "test-secret-api-key-123"}
            )
            assert res_settings_authed.status_code == 200

    finally:
        app_settings.REQUIRE_AUTH = original_require_auth
        app_settings.API_KEY = original_api_key


def test_session_ownership_isolation(tmp_path):
    """Verify that client A cannot access or modify client B's documents and templates."""
    import docx

    with TestClient(app) as client:
        # Create dummy docx
        doc_path = tmp_path / "alice_contract.docx"
        doc = docx.Document()
        doc.add_paragraph("Alice's confidential agreement with Acme Corp.")
        doc.save(str(doc_path))

        alice_session = "session_alice_999"
        bob_session = "session_bob_888"

        # Alice uploads document
        with open(doc_path, "rb") as f:
            res = client.post(
                "/api/v1/documents",
                files={"file": ("alice_contract.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                headers={"X-Session-ID": alice_session},
            )
        assert res.status_code == 201
        doc_id = res.json()["id"]

        # Alice can get her document
        res_alice = client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Session-ID": alice_session},
        )
        assert res_alice.status_code == 200

        # Bob tries to get Alice's document -> 403 Forbidden
        res_bob_get = client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Session-ID": bob_session},
        )
        assert res_bob_get.status_code == 403

        # Bob tries to analyze Alice's document -> 403 Forbidden
        res_bob_analyze = client.post(
            f"/api/v1/documents/{doc_id}/analyze",
            headers={"X-Session-ID": bob_session},
        )
        assert res_bob_analyze.status_code == 403

        # Bob tries to delete Alice's document -> 403 Forbidden
        res_bob_delete = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Session-ID": bob_session},
        )
        assert res_bob_delete.status_code == 403

        # Alice creates a template
        res_template = client.post(
            "/api/v1/templates",
            headers={"X-Session-ID": alice_session},
            json={
                "name": "Alice's Template",
                "document_id": doc_id,
                "variables": [],
                "occurrences": [],
            },
        )
        assert res_template.status_code == 201
        template_id = res_template.json()["id"]

        # Bob tries to access Alice's template -> 403 Forbidden
        res_bob_template = client.get(
            f"/api/v1/templates/{template_id}",
            headers={"X-Session-ID": bob_session},
        )
        assert res_bob_template.status_code == 403

        # Bob tries to generate from Alice's template -> 403 Forbidden
        res_bob_generate = client.post(
            f"/api/v1/templates/{template_id}/generate",
            headers={"X-Session-ID": bob_session},
            json={"values": {}},
        )
        assert res_bob_generate.status_code == 403

        # Alice can access her template
        res_alice_template = client.get(
            f"/api/v1/templates/{template_id}",
            headers={"X-Session-ID": alice_session},
        )
        assert res_alice_template.status_code == 200

        # Alice can delete her document
        res_alice_delete = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Session-ID": alice_session},
        )
        assert res_alice_delete.status_code == 200
