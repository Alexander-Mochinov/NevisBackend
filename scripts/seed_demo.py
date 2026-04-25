"""Seed a small demo dataset through the public API.

The script intentionally uses only the Python standard library so reviewers do
not need extra CLI tools such as jq.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
CLIENT_EMAIL = "sample.client@neviswealth.test"


def main() -> int:
    try:
        client = create_or_get_client()
        document = post_json(
            f"/clients/{client['id']}/documents",
            {
                "title": "Utility Bill",
                "content": (
                    "The client uploaded a recent utility bill as proof of residence "
                    "and address verification."
                ),
            },
        )
    except (HTTPError, URLError, RuntimeError) as exc:
        print(f"Demo seed failed: {exc}", file=sys.stderr)
        return 1

    print("Demo data is ready.")
    print(f"Client: {client['id']} {client['email']}")
    print(f"Document: {document['id']} {document['title']}")
    print(f"Try: {API_BASE_URL}/search?q=NevisWealth")
    print(f"Try: {API_BASE_URL}/search?q=address%20proof")
    print(f"Try: {API_BASE_URL}/search?q=utlity%20bil")
    return 0


def create_or_get_client() -> dict[str, Any]:
    payload = {
        "first_name": "Sample",
        "last_name": "Client",
        "email": CLIENT_EMAIL,
        "description": "Wealth management client",
        "social_links": ["https://example.test/profiles/sample-client"],
    }

    try:
        return post_json("/clients", payload)
    except HTTPError as exc:
        if exc.code != 409:
            raise

    search_results = get_json("/search", {"q": "NevisWealth"})
    for result in search_results:
        client = result.get("client")
        if isinstance(client, dict) and client.get("email") == CLIENT_EMAIL:
            return client

    raise RuntimeError("Client already exists, but could not be found through search.")


def post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{API_BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def get_json(path: str, params: dict[str, str]) -> list[dict[str, Any]]:
    query = urlencode(params)
    with urlopen(f"{API_BASE_URL}{path}?{query}", timeout=10) as response:
        data = json.load(response)

    if not isinstance(data, list):
        raise RuntimeError(f"Expected list response from {path}; got {type(data).__name__}.")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
