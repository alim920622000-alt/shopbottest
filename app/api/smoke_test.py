from __future__ import annotations

import json
import os
import urllib.request


BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
TELEGRAM_USER_ID = int(os.getenv("API_SMOKE_TELEGRAM_USER_ID", "1"))


def _post(path: str, payload: dict, token: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    auth = _post("/auth/telegram", {"telegram_user_id": TELEGRAM_USER_ID})
    token = auth["access_token"]
    merchants = _get("/catalog/merchants?type=shop&limit=5", token)
    print("TOKEN:", token)
    print("MERCHANTS:", json.dumps(merchants, ensure_ascii=False))


if __name__ == "__main__":
    main()
