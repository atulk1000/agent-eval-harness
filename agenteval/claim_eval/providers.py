"""Provider-neutral semantic claim-judge interfaces."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

PROMPT_VERSION = "claim_support_v1"


class JudgeProviderError(RuntimeError):
    """A semantic provider failed before returning a usable verdict."""


class JudgeProviderTimeout(JudgeProviderError):
    """A semantic provider exceeded its timeout."""


class SemanticJudgeProvider(Protocol):
    name: str
    model: str

    def judge(self, claim: dict[str, Any], evidence: list[dict[str, Any]]) -> ProviderResponse: ...


@dataclass
class ProviderResponse:
    output: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    redacted: bool = False
    attempts: int = 1


class RuleOnlyJudgeProvider:
    name = "rule_only"
    model = "rules-v1"

    def judge(self, claim: dict[str, Any], evidence: list[dict[str, Any]]) -> ProviderResponse:
        raise JudgeProviderError("rule-only provider does not perform semantic calls")


class MockJudgeProvider:
    name = "mock"

    def __init__(
        self,
        responses: dict[str, dict[str, Any]] | None = None,
        *,
        default: dict[str, Any] | None = None,
        failure: str | None = None,
        model: str = "mock-v1",
    ) -> None:
        self.responses = responses or {}
        self.default = default or {
            "verdict": "supported",
            "confidence": 0.8,
            "reason": "Mock semantic evidence match.",
            "evidence_refs": [],
            "unsupported_parts": [],
        }
        self.failure = failure
        self.model = model
        self.calls = 0

    def judge(self, claim: dict[str, Any], evidence: list[dict[str, Any]]) -> ProviderResponse:
        self.calls += 1
        if self.failure == "timeout":
            raise JudgeProviderTimeout("mock timeout")
        if self.failure:
            raise JudgeProviderError(self.failure)
        output = dict(self.responses.get(claim["claim_id"], self.default))
        if output.get("evidence_refs") == [] and evidence:
            output["evidence_refs"] = [evidence[0]["evidence_id"]]
        return ProviderResponse(output=output, input_tokens=25, output_tokens=12)


class OpenAICompatibleJudgeProvider:
    """Call a JSON-capable Chat Completions-compatible endpoint.

    A request function can be injected for private gateways and offline tests. It
    receives the request payload and returns the decoded response object.
    """

    name = "openai_compatible"

    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        request_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        redaction_hook: Callable[[str], str] | None = None,
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.request_fn = request_fn
        self.redaction_hook = redaction_hook or (lambda value: value)

    def judge(self, claim: dict[str, Any], evidence: list[dict[str, Any]]) -> ProviderResponse:
        context = json.dumps({"claim": claim, "evidence": evidence}, sort_keys=True)
        redacted = self.redaction_hook(context)
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Judge only whether the claim is supported by the supplied evidence. "
                        "Return JSON with verdict, confidence, reason, evidence_refs, and unsupported_parts. "
                        "Allowed verdicts: supported, partially_supported, unsupported, contradicted, "
                        "not_enough_evidence. Do not use outside knowledge."
                    ),
                },
                {"role": "user", "content": redacted},
            ],
            "response_format": {"type": "json_object"},
        }
        response, attempts = self._call(payload)
        output, usage = _decode_response(response)
        return ProviderResponse(
            output=output,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            redacted=redacted != context,
            attempts=attempts,
        )

    def extract(self, answer: str) -> list[dict[str, Any]]:
        redacted = self.redaction_hook(answer)
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract atomic factual propositions from the answer. Return JSON with a claims array. "
                        "Each claim needs text, source_text, source_span with start and end, claim_type, "
                        "assertion_mode, subject, and source_requirement. Do not add facts."
                    ),
                },
                {"role": "user", "content": redacted},
            ],
            "response_format": {"type": "json_object"},
        }
        response, _ = self._call(payload)
        output, _ = _decode_response(response)
        claims = output.get("claims")
        if not isinstance(claims, list):
            raise JudgeProviderError("semantic extraction response must contain a claims array")
        return claims

    def _call(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        last_error: JudgeProviderError | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.request_fn(payload) if self.request_fn else self._request(payload)
                return response, attempt
            except TimeoutError as exc:
                last_error = JudgeProviderTimeout(str(exc))
            except JudgeProviderError as exc:
                last_error = exc
        if last_error is None:
            raise JudgeProviderError("provider call failed without an error")
        raise last_error

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = (
            self.endpoint
            if self.endpoint.endswith("/chat/completions")
            else f"{self.endpoint}/chat/completions"
        )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise JudgeProviderTimeout(str(exc.reason)) from exc
            raise JudgeProviderError(str(exc)) from exc


def _decode_response(response: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if "verdict" in response:
        return response, {}
    try:
        content = response["choices"][0]["message"]["content"]
        output = json.loads(content) if isinstance(content, str) else content
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise JudgeProviderError("provider returned an unreadable structured response") from exc
    if not isinstance(output, dict):
        raise JudgeProviderError("provider verdict output must be a JSON object")
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return output, usage
