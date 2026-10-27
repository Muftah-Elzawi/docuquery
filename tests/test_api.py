"""End-to-end tests through the HTTP API, against a real Postgres + pgvector."""

from conftest import register, upload


def test_upload_extracts_fields_and_answers_with_citations(client, sample_dir):
    h = register(client, "Inntal Logistik", "admin@inntal.example")
    doc = upload(client, h, sample_dir / "rechnung_alpenblick_2026-0412.pdf")
    assert doc["status"] == "ready"
    assert doc["extracted_fields"]["document_number"] == "RE-2026-0412"
    assert doc["extracted_fields"]["gross_amount"] == "1428.00"

    upload(client, h, sample_dir / "reisekostenrichtlinie_inntal.pdf")
    r = client.post("/api/ask", headers=h, json={"question": "Wie hoch ist die Verpflegung Pauschale fuer volle Kalendertage?"})
    assert r.status_code == 200
    top = r.json()["sources"][0]
    assert top["filename"] == "reisekostenrichtlinie_inntal.pdf"
    assert top["page"] == 2  # citation points to the right page
    assert "28 EUR" in top["excerpt"]


def test_plausibility_warning_for_wrong_totals(client, sample_dir):
    h = register(client, "Inntal Logistik", "admin@inntal.example")
    doc = upload(client, h, sample_dir / "rechnung_fehlerhaft_2026-0419.pdf")
    assert any("don't add up" in w for w in doc["extracted_fields"]["warnings"])


def test_workspaces_are_isolated(client, sample_dir):
    a = register(client, "Company A", "a@a.example")
    b = register(client, "Company B", "b@b.example")
    doc = upload(client, a, sample_dir / "reisekostenrichtlinie_inntal.pdf")

    assert client.get("/api/documents", headers=b).json() == []
    assert client.get(f"/api/documents/{doc['id']}", headers=b).status_code == 404
    assert client.delete(f"/api/documents/{doc['id']}", headers=b).status_code == 404
    r = client.post("/api/ask", headers=b, json={"question": "Hotelkosten pro Nacht?"})
    assert r.json()["sources"] == []  # B's search never sees A's chunks


def test_roles(client, sample_dir):
    admin = register(client, "Inntal Logistik", "admin@inntal.example")
    r = client.post("/api/admin/users", headers=admin,
                    json={"email": "member@inntal.example", "password": "secret-123", "role": "member"})
    assert r.status_code == 201
    token = client.post("/api/auth/login", data={"username": "member@inntal.example", "password": "secret-123"}).json()
    member = {"Authorization": f"Bearer {token['access_token']}"}

    assert client.get("/api/admin/stats", headers=member).status_code == 403
    doc = upload(client, admin, sample_dir / "reisekostenrichtlinie_inntal.pdf")
    assert client.get("/api/documents", headers=member).json()[0]["id"] == doc["id"]  # same workspace
    assert client.delete(f"/api/documents/{doc['id']}", headers=member).status_code == 403
    assert client.get("/api/admin/stats", headers=admin).json()["users"] == 2


def test_auth_errors(client):
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/documents", headers={"Authorization": "Bearer nope"}).status_code == 401
    register(client, "Test GmbH", "x@x.example")
    bad = client.post("/api/auth/login", data={"username": "x@x.example", "password": "wrong-pass"})
    assert bad.status_code == 401


def test_rejects_non_pdf(client):
    h = register(client, "Test GmbH", "x@x.example")
    r = client.post("/api/documents", headers=h, files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415
