"""Workstation-side GitHub App auth: mint an installation token, then a runner registration token.

Used during the deploy's prepare phase only when the persistent release runner has to be
registered; nothing here runs on the Mac. The App's private key never leaves the workstation for
this purpose (the host gets its own copy for JIT configs, delivered by tasks/github_app.py).
"""

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


def app_jwt(app_id: str, key_path: str) -> str:
    key = serialization.load_pem_private_key(open(key_path, "rb").read(), password=None)
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}).encode())
    signature = _b64url(key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    return f"{header}.{payload}.{signature}"


def _call(method: str, path: str, bearer: str) -> dict:
    request = urllib.request.Request(
        API + path,
        method=method,
        data=b"{}" if method == "POST" else None,
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response) if response.status != 204 else {}


def _post(path: str, bearer: str) -> dict:
    return _call("POST", path, bearer)


def installation_token(app_id: str, installation_id: str, key_path: str) -> str:
    return _post(f"/app/installations/{installation_id}/access_tokens", app_jwt(app_id, key_path))["token"]


def registration_token(repo: str, installation_token: str) -> str:
    """Short-lived (1 h) token for `config.sh --token`."""
    return _post(f"/repos/{repo}/actions/runners/registration-token", installation_token)["token"]


def list_runners(repo: str, installation_token: str) -> list[dict]:
    return _call("GET", f"/repos/{repo}/actions/runners?per_page=100", installation_token)["runners"]


def delete_runner(repo: str, installation_token: str, runner_id: int) -> None:
    _call("DELETE", f"/repos/{repo}/actions/runners/{runner_id}", installation_token)
