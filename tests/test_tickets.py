from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import STORE

VALID = {"title": "Cannot start the server", "body": "uvicorn exits immediately on startup"}


@pytest.fixture(autouse=True)
def _reset_store():
    """Each test starts with an empty store and ids restarting at 1."""
    STORE.__init__()


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_exactly_five_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    operations = {(m.upper(), p) for p, ops in paths.items() for m in ops}
    assert operations == {
        ("GET", "/health"),
        ("POST", "/tickets"),
        ("GET", "/tickets"),
        ("GET", "/tickets/{ticket_id}"),
        ("PATCH", "/tickets/{ticket_id}"),
    }


# --- POST /tickets -----------------------------------------------------------


def test_create_returns_201_with_server_fields(client):
    r = client.post("/tickets", json=VALID)
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == 1
    assert data["status"] == "open"
    assert data["created_at"]
    assert data["fastapi_version"] is None
    assert data["title"] == VALID["title"]


@pytest.mark.parametrize("fake_created_at", ["2000-01-01T00:00:00Z", "2099-12-31T23:59:59Z"])
def test_client_cannot_set_id_status_or_created_at(client, fake_created_at):
    before = datetime.now(timezone.utc)
    r = client.post(
        "/tickets",
        json={**VALID, "id": 999, "status": "closed", "created_at": fake_created_at},
    )
    after = datetime.now(timezone.utc)

    assert r.status_code == 201
    data = r.json()
    assert data["id"] == 1  # not 999
    assert data["status"] == "open"  # not "closed"
    # created_at is the server's clock at request time, not the client's value
    assert before <= datetime.fromisoformat(data["created_at"]) <= after
    # and the stored ticket agrees with what was returned
    assert client.get("/tickets/1").json() == data


@pytest.mark.parametrize(
    "payload",
    [
        {**VALID, "title": "abc"},  # too short
        {**VALID, "title": "x" * 201},  # too long
        {**VALID, "title": "     "},  # whitespace only
        {**VALID, "body": "short"},  # body too short
        {"title": VALID["title"]},  # body missing
        {},
    ],
)
def test_create_invalid_input_is_422(client, payload):
    assert client.post("/tickets", json=payload).status_code == 422


# --- GET /tickets/{id} -------------------------------------------------------


def test_get_one(client):
    created = client.post("/tickets", json=VALID).json()
    r = client.get(f"/tickets/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


def test_get_missing_is_404(client):
    r = client.get("/tickets/42")
    assert r.status_code == 404
    assert "42" in r.json()["detail"]


def test_get_non_integer_id_is_422(client):
    assert client.get("/tickets/abc").status_code == 422


# --- GET /tickets ------------------------------------------------------------


def test_list_empty(client):
    r = client.get("/tickets")
    assert r.status_code == 200
    assert r.json() == []


def test_list_filter_by_status(client):
    for _ in range(3):
        client.post("/tickets", json=VALID)
    client.patch("/tickets/2", json={"status": "closed"})

    assert len(client.get("/tickets").json()) == 3
    closed = client.get("/tickets", params={"status": "closed"}).json()
    assert [t["id"] for t in closed] == [2]
    open_ = client.get("/tickets", params={"status": "open"}).json()
    assert [t["id"] for t in open_] == [1, 3]


def test_list_pagination(client):
    for _ in range(5):
        client.post("/tickets", json=VALID)
    page = client.get("/tickets", params={"limit": 2, "offset": 1}).json()
    assert [t["id"] for t in page] == [2, 3]


@pytest.mark.parametrize(
    "params",
    [{"status": "bogus"}, {"limit": 0}, {"limit": 10_000}, {"offset": -1}],
)
def test_list_bad_query_is_422(client, params):
    assert client.get("/tickets", params=params).status_code == 422


# --- PATCH /tickets/{id} -----------------------------------------------------


def test_patch_one_field_leaves_others_unchanged(client):
    original = client.post("/tickets", json={**VALID, "fastapi_version": "0.115.0"}).json()

    r = client.patch("/tickets/1", json={"status": "answered"})
    assert r.status_code == 200
    assert r.json() == {**original, "status": "answered"}

    r = client.patch("/tickets/1", json={"title": "A brand new title"})
    assert r.status_code == 200
    assert r.json() == {**original, "status": "answered", "title": "A brand new title"}

    # and the change really persisted
    assert client.get("/tickets/1").json() == r.json()


def test_patch_empty_body_is_a_noop(client):
    original = client.post("/tickets", json=VALID).json()
    r = client.patch("/tickets/1", json={})
    assert r.status_code == 200
    assert r.json() == original


def test_patch_cannot_change_id_or_created_at(client):
    original = client.post("/tickets", json=VALID).json()
    r = client.patch("/tickets/1", json={"id": 7, "created_at": "2000-01-01T00:00:00Z", "body": "hacked"})
    assert r.status_code == 200
    assert r.json() == original


def test_patch_missing_is_404(client):
    assert client.patch("/tickets/42", json={"status": "closed"}).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "bogus"},
        {"title": "abc"},
        {"title": None},  # explicit null must not wipe a required field
        {"status": None},
    ],
)
def test_patch_invalid_input_is_422(client, payload):
    client.post("/tickets", json=VALID)
    assert client.patch("/tickets/1", json=payload).status_code == 422
    # the stored ticket is untouched by a rejected PATCH
    assert client.get("/tickets/1").json()["title"] == VALID["title"]
