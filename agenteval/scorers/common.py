"""Shared scoring helpers."""

from __future__ import annotations

import re
from typing import Any


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def contains_term(text: str, term: str) -> bool:
    return normalize(term) in normalize(text)


def tool_events(run: dict[str, Any], tool: str | None = None) -> list[dict[str, Any]]:
    events = [event for event in run.get("trace", []) if event.get("type") == "tool_call"]
    if tool is not None:
        return [event for event in events if event.get("tool") == tool]
    return events


def actual_route(run: dict[str, Any]) -> list[str]:
    return [event.get("tool", "") for event in tool_events(run)]


def unique_route(run: dict[str, Any]) -> list[str]:
    seen = set()
    route = []
    for tool in actual_route(run):
        if tool not in seen:
            route.append(tool)
            seen.add(tool)
    return route


def successful_events(run: dict[str, Any], tool: str) -> list[dict[str, Any]]:
    return [event for event in tool_events(run, tool) if event.get("success")]


def row_entities(run: dict[str, Any]) -> set[str]:
    entities: set[str] = set()
    for event in successful_events(run, "sql_query"):
        for row in event.get("output", {}).get("rows", []):
            for key in ("customer_name", "customer", "name"):
                value = row.get(key)
                if isinstance(value, str):
                    entities.add(value)
    return entities


def tables_used(run: dict[str, Any]) -> set[str]:
    tables: set[str] = set()
    for event in tool_events(run, "sql_query"):
        for table in event.get("output", {}).get("tables_used", []):
            tables.add(str(table).lower())
    return tables


def retrieved_doc_ids(run: dict[str, Any]) -> set[str]:
    doc_ids: set[str] = set()
    for event in successful_events(run, "rag_search"):
        for doc in event.get("output", {}).get("documents", []):
            doc_id = doc.get("doc_id")
            if isinstance(doc_id, str):
                doc_ids.add(doc_id)
    for event in successful_events(run, "document_lookup"):
        doc = event.get("output", {}).get("document")
        if isinstance(doc, dict) and isinstance(doc.get("doc_id"), str):
            doc_ids.add(doc["doc_id"])
    return doc_ids


def evidence_text(run: dict[str, Any]) -> str:
    chunks: list[str] = []
    for event in successful_events(run, "sql_query"):
        chunks.append(str(event.get("output", {}).get("rows", [])))
    for event in successful_events(run, "rag_search"):
        for doc in event.get("output", {}).get("documents", []):
            chunks.append(str(doc.get("text", "")))
    for event in successful_events(run, "document_lookup"):
        doc = event.get("output", {}).get("document")
        if isinstance(doc, dict):
            chunks.append(str(doc.get("text", "")))
    return "\n".join(chunks)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
