"""Minimal GitHub App auth for the dynamic provider (installation tokens from the App's key)."""

from __future__ import annotations

import base64
import json
import time
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API = "https://api.github.com"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def app_jwt(app_id: str, pem: str) -> str:
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}).encode())
    signature = _b64url(key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    return f"{header}.{payload}.{signature}"


def api(method: str, path: str, bearer: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response) if response.status != 204 else {}


def installation_token(app_id: str, installation_id: str, pem: str) -> str:
    return api("POST", f"/app/installations/{installation_id}/access_tokens", app_jwt(app_id, pem), {})["token"]
