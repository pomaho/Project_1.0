from __future__ import annotations

import httpx

from app.config import settings

MEILI_INDEX = "files"


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.meili_key:
        headers["Authorization"] = f"Bearer {settings.meili_key}"
    return headers


def get_client() -> httpx.Client:
    return httpx.Client(base_url=settings.meili_url, headers=_headers(), timeout=10.0)


def ensure_index(client: httpx.Client) -> None:
    resp = client.get(f"/indexes/{MEILI_INDEX}")
    if resp.status_code == 404:
        client.post("/indexes", json={"uid": MEILI_INDEX, "primaryKey": "id"})
    elif resp.status_code >= 400:
        resp.raise_for_status()
    settings_payload = {
        "searchableAttributes": ["keywords", "filename", "title", "description"],
        "filterableAttributes": [
            "orientation",
            "shot_at",
            "mtime",
            "keywords_norm",
            "collections",
            "deleted",
        ],
        "sortableAttributes": ["shot_at", "mtime"],
        "pagination": {"maxTotalHits": settings.meili_max_total_hits},
    }
    client.patch(f"/indexes/{MEILI_INDEX}/settings", json=settings_payload)


def upsert_documents(client: httpx.Client, docs: list[dict]) -> None:
    client.post(f"/indexes/{MEILI_INDEX}/documents", json=docs)


def delete_document(client: httpx.Client, doc_id: str) -> None:
    client.delete(f"/indexes/{MEILI_INDEX}/documents/{doc_id}")


def search_documents(client: httpx.Client, payload: dict) -> dict:
    ensure_index(client)
    resp = client.post(f"/indexes/{MEILI_INDEX}/search", json=payload)
    resp.raise_for_status()
    return resp.json()
