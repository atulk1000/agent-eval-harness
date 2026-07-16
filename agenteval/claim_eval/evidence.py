"""Trace-only evidence construction and claim-specific candidate selection."""

from __future__ import annotations

import json
import re
from typing import Any

from agenteval.claim_eval.models import SCHEMA_VERSION, stable_id, validate_evidence

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "which",
    "with",
}


class TraceEvidenceBuilder:
    """Build evidence exclusively from tool events captured in a run."""

    def build(self, run: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        run_id = str(run.get("run_id") or f"run_{run.get('task_id', 'unknown')}")
        task_id = str(run.get("task_id", "unknown"))
        for event_index, event in enumerate(run.get("trace", []), start=1):
            step = int(event.get("step") or event_index)
            tool = str(event.get("tool", "unknown"))
            output = event.get("output") if isinstance(event.get("output"), dict) else {}
            if not event.get("success", False):
                records.append(
                    self._record(
                        run_id,
                        task_id,
                        step,
                        tool,
                        "tool_error",
                        0,
                        str(event.get("error") or "Tool call failed."),
                        {"error": event.get("error")},
                    )
                )
                continue
            if tool == "sql_query":
                rows = output.get("rows") if isinstance(output.get("rows"), list) else []
                if not rows:
                    records.append(
                        self._empty(run_id, task_id, step, tool, "SQL query returned no rows.")
                    )
                for index, row in enumerate(rows):
                    payload = row if isinstance(row, dict) else {"value": row}
                    records.append(
                        self._record(
                            run_id,
                            task_id,
                            step,
                            tool,
                            "sql_row",
                            index,
                            _content(payload),
                            payload,
                            event.get("input"),
                        )
                    )
            elif tool == "rag_search":
                documents = output.get("documents")
                if not isinstance(documents, list):
                    documents = (
                        output.get("chunks") if isinstance(output.get("chunks"), list) else []
                    )
                if not documents:
                    records.append(
                        self._empty(run_id, task_id, step, tool, "Retrieval returned no documents.")
                    )
                for index, document in enumerate(documents):
                    payload = document if isinstance(document, dict) else {"text": str(document)}
                    records.append(
                        self._record(
                            run_id,
                            task_id,
                            step,
                            tool,
                            "document_chunk",
                            index,
                            str(payload.get("text") or payload.get("content") or _content(payload)),
                            payload,
                        )
                    )
            elif tool == "document_lookup":
                document = output.get("document")
                if not isinstance(document, dict):
                    records.append(
                        self._empty(
                            run_id, task_id, step, tool, "Document lookup returned no document."
                        )
                    )
                else:
                    records.append(
                        self._record(
                            run_id,
                            task_id,
                            step,
                            tool,
                            "opened_document",
                            0,
                            str(
                                document.get("text")
                                or document.get("content")
                                or _content(document)
                            ),
                            document,
                        )
                    )
        return records

    def _empty(
        self, run_id: str, task_id: str, step: int, tool: str, content: str
    ) -> dict[str, Any]:
        return self._record(run_id, task_id, step, tool, "empty_result", 0, content, {})

    def _record(
        self,
        run_id: str,
        task_id: str,
        step: int,
        tool: str,
        source_type: str,
        index: int,
        content: str,
        payload: dict[str, Any],
        tool_input: Any = None,
    ) -> dict[str, Any]:
        record = {
            "schema_version": SCHEMA_VERSION,
            "evidence_id": stable_id("evidence", run_id, step, source_type, index),
            "run_id": run_id,
            "task_id": task_id,
            "source_type": source_type,
            "tool": tool,
            "tool_step": step,
            "content": content,
            "structured_payload": payload,
            "provenance": {
                "trace_run_id": run_id,
                "event_step": step,
                "item_index": index,
                "tool_input": tool_input,
            },
        }
        return validate_evidence(record)


class EvidenceSelector:
    def __init__(self, limit: int = 8) -> None:
        if limit < 1:
            raise ValueError("evidence candidate limit must be positive")
        self.limit = limit

    def select(
        self, claim: dict[str, Any], evidence: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        scored = [(self._score(claim, item), index, item) for index, item in enumerate(evidence)]
        scored.sort(key=lambda item: (-item[0], item[1]))
        positive = [item for score, _, item in scored if score > 0]
        diagnostic = [
            item
            for score, _, item in scored
            if score == 0 and item["source_type"] in {"tool_error", "empty_result"}
        ]
        candidates = (positive + diagnostic)[: self.limit]
        return candidates, {
            "candidate_limit": self.limit,
            "candidate_count": len(candidates),
            "excluded_count": max(0, len(evidence) - len(candidates)),
        }

    def _score(self, claim: dict[str, Any], item: dict[str, Any]) -> float:
        requirement = claim.get("source_requirement", "any")
        source_type = item["source_type"]
        source_match = (
            requirement in {"any", "hybrid"}
            or requirement == "sql"
            and source_type == "sql_row"
            or requirement == "rag"
            and source_type in {"document_chunk", "opened_document"}
        )
        if source_type in {"tool_error", "empty_result"}:
            return 0.1 if source_match or requirement in {"any", "hybrid"} else 0.0
        claim_tokens = _tokens(str(claim.get("text", "")))
        evidence_tokens = _tokens(
            item.get("content", "") + " " + _content(item.get("structured_payload", {}))
        )
        overlap = len(claim_tokens & evidence_tokens) / max(len(claim_tokens), 1)
        subject = str(claim.get("subject") or "").lower()
        subject_bonus = 1.5 if subject and subject in item.get("content", "").lower() else 0.0
        claim_numbers = set(re.findall(r"-?\d+(?:\.\d+)?%?", str(claim.get("text", ""))))
        evidence_numbers = set(re.findall(r"-?\d+(?:\.\d+)?%?", item.get("content", "")))
        number_bonus = 1.0 if claim_numbers and claim_numbers <= evidence_numbers else 0.0
        return overlap + subject_bonus + number_bonus + (0.25 if source_match else 0.0)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", text.lower())
        if token not in STOPWORDS and len(token) > 1
    }


def _content(payload: Any) -> str:
    if isinstance(payload, dict):
        return ", ".join(f"{key}={_scalar(value)}" for key, value in sorted(payload.items()))
    return _scalar(payload)


def _scalar(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)
