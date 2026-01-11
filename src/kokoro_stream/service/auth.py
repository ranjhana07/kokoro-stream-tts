from __future__ import annotations

import hmac
from typing import Iterable, Mapping

OPEN_ENDPOINTS = frozenset({"healthz", "metrics_endpoint", "static"})


def extract_token(headers: Mapping[str, str]) -> str:
    authorization = headers.get("Authorization", "")
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() == "bearer" and credential:
        return credential.strip()
    return headers.get("X-API-Key", "").strip()


def is_authorized(token: str, api_keys: Iterable[str]) -> bool:
    if not token:
        return False
    matched = False
    for key in api_keys:
        if hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8")):
            matched = True
    return matched
