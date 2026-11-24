from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)


def setup_function():
    store.clear()


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_shorten_and_redirect():
    r = client.post("/shorten", json={"url": "https://example.com"})
    assert r.status_code == 201
    code = r.json()["code"]
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com"


def test_stats_counts_clicks():
    code = client.post("/shorten", json={"url": "https://example.com"}).json()["code"]
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)
    assert client.get(f"/stats/{code}").json()["clicks"] == 2


def test_invalid_url_rejected():
    for bad in ["javascript:alert(1)", "file:///etc/passwd", "not a url"]:
        assert client.post("/shorten", json={"url": bad}).status_code == 400


def test_unknown_code_404():
    assert client.get("/nope", follow_redirects=False).status_code == 404
    assert client.get("/stats/nope").status_code == 404