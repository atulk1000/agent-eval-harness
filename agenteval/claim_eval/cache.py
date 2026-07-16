"""Deterministic semantic-judge cache."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key(
    claim: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    provider: str,
    model: str,
    prompt_version: str,
) -> str:
    payload = {
        "schema_version": "1.0",
        "claim": claim,
        "evidence": evidence,
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class JudgeCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._entries: dict[str, dict[str, Any]] = {}
        if self.path and self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._entries = loaded

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._entries.get(key)
        return dict(value) if value is not None else None

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._entries[key] = dict(value)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._entries, indent=2, sort_keys=True), encoding="utf-8"
            )
