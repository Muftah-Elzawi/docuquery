import os
import sys
from pathlib import Path

import pytest

# Must be set before the app is imported: tests run against a real Postgres + pgvector,
# with the offline FakeProvider instead of a real model.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/docuquery_test")
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_DIM"] = "256"
os.environ["MIN_SIMILARITY"] = "0.1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from make_sample_docs import main as make_sample_docs  # noqa: E402


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("samples")
    make_sample_docs(str(out))
    return out


@pytest.fixture()
def client():
    from app.db import init_db

    init_db()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def register(client, workspace: str, email: str, password: str = "secret-123") -> dict:
    r = client.post("/api/auth/register", json={"workspace_name": workspace, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def upload(client, headers: dict, path: Path) -> dict:
    with path.open("rb") as f:
        r = client.post("/api/documents", headers=headers, files={"file": (path.name, f, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()
