import secrets
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="URL Shortener")
store: dict[str, dict] = {}  # code -> {"url": ..., "clicks": ...}


class ShortenRequest(BaseModel):
    url: str


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@app.post("/shorten", status_code=201)
def shorten(req: ShortenRequest):
    if not is_valid_url(req.url):
        raise HTTPException(status_code=400, detail="Only valid http(s) URLs are allowed")
    code = secrets.token_urlsafe(5)
    store[code] = {"url": req.url, "clicks": 0}
    return {"code": code, "short_path": f"/{code}"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats/{code}")
def stats(code: str):
    if code not in store:
        raise HTTPException(status_code=404, detail="Code not found")
    return {"code": code, **store[code]}


# Must stay LAST: this route matches almost any path.
@app.get("/{code}")
def redirect(code: str):
    if code not in store:
        raise HTTPException(status_code=404, detail="Code not found")
    store[code]["clicks"] += 1
    return RedirectResponse(store[code]["url"], status_code=307)