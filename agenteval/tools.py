"""Traced demo tools for SQL + RAG agents."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from agenteval.data_loader import DEFAULT_DB_PATH, DEFAULT_DOCS_PATH, load_documents
from agenteval.trace import TraceRecorder, timed_call

TABLE_PATTERN = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)


def schema_lookup(
    recorder: TraceRecorder,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    tables: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect the SQLite schema."""

    def work() -> dict[str, Any]:
        with closing(sqlite3.connect(db_path)) as conn:
            available = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]
            selected = tables or available
            schema = {}
            for table in selected:
                if table not in available:
                    schema[table] = {"error": "table not found"}
                    continue
                columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
                schema[table] = [
                    {"name": column[1], "type": column[2], "nullable": not bool(column[3])}
                    for column in columns
                ]
            return {"tables": schema}

    output, latency_ms = timed_call(work)
    return recorder.record_tool(
        "schema_lookup",
        {"tables": tables or []},
        output,
        latency_ms=latency_ms,
    )


def _is_read_only_sql(query: str) -> bool:
    stripped = query.strip().lower()
    if not stripped:
        return False
    if ";" in stripped[:-1]:
        return False
    return stripped.startswith("select") or stripped.startswith("with")


def _tables_used(query: str) -> list[str]:
    return sorted({match.group(1).lower() for match in TABLE_PATTERN.finditer(query)})


def sql_query(
    recorder: TraceRecorder,
    query: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Run a read-only SQL query and record rows or errors."""

    tool_input = {"query": query}
    if not _is_read_only_sql(query):
        output = {"rows": [], "columns": [], "tables_used": _tables_used(query)}
        return recorder.record_tool(
            "sql_query",
            tool_input,
            output,
            success=False,
            error="unsafe_sql_only_select_allowed",
        )

    def work() -> dict[str, Any]:
        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query)
            rows = [dict(row) for row in cursor.fetchall()]
            columns = [description[0] for description in cursor.description or []]
            return {"rows": rows, "columns": columns, "tables_used": _tables_used(query)}

    try:
        output, latency_ms = timed_call(work)
        return recorder.record_tool(
            "sql_query",
            tool_input,
            output,
            latency_ms=latency_ms,
        )
    except sqlite3.Error as exc:
        return recorder.record_tool(
            "sql_query",
            tool_input,
            {"rows": [], "columns": [], "tables_used": _tables_used(query)},
            success=False,
            error=str(exc),
        )


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token
        not in {
            "the",
            "and",
            "or",
            "a",
            "an",
            "to",
            "of",
            "for",
            "in",
            "with",
            "is",
            "are",
            "do",
            "does",
            "which",
            "what",
        }
    }


def rag_search(
    recorder: TraceRecorder,
    query: str,
    *,
    docs_path: str | Path = DEFAULT_DOCS_PATH,
    top_k: int = 3,
) -> dict[str, Any]:
    """Run simple lexical retrieval over the demo corpus."""

    def work() -> dict[str, Any]:
        query_tokens = _tokens(query)
        results = []
        for doc in load_documents(docs_path):
            text = f"{doc['title']} {doc.get('customer') or ''} {doc['doc_type']} {doc['text']}"
            doc_tokens = _tokens(text)
            overlap = query_tokens & doc_tokens
            score = len(overlap) / max(len(query_tokens), 1)
            if score > 0:
                results.append(
                    {
                        "doc_id": doc["doc_id"],
                        "title": doc["title"],
                        "customer": doc.get("customer"),
                        "doc_type": doc["doc_type"],
                        "score": round(score, 3),
                        "text": doc["text"],
                    }
                )
        results.sort(key=lambda item: (-item["score"], item["doc_id"]))
        return {"documents": results[:top_k]}

    output, latency_ms = timed_call(work)
    return recorder.record_tool(
        "rag_search",
        {"query": query, "top_k": top_k},
        output,
        latency_ms=latency_ms,
    )


def document_lookup(
    recorder: TraceRecorder,
    doc_id: str,
    *,
    docs_path: str | Path = DEFAULT_DOCS_PATH,
) -> dict[str, Any]:
    """Open one document from the demo corpus."""

    def work() -> dict[str, Any]:
        for doc in load_documents(docs_path):
            if doc["doc_id"] == doc_id:
                return {"document": doc}
        raise KeyError(doc_id)

    try:
        output, latency_ms = timed_call(work)
        return recorder.record_tool(
            "document_lookup",
            {"doc_id": doc_id},
            output,
            latency_ms=latency_ms,
        )
    except KeyError:
        return recorder.record_tool(
            "document_lookup",
            {"doc_id": doc_id},
            {"document": None},
            success=False,
            error=f"document not found: {doc_id}",
        )


class Toolset:
    """Convenience wrapper passed to demo agents."""

    def __init__(
        self,
        recorder: TraceRecorder,
        *,
        db_path: str | Path = DEFAULT_DB_PATH,
        docs_path: str | Path = DEFAULT_DOCS_PATH,
    ) -> None:
        self.recorder = recorder
        self.db_path = db_path
        self.docs_path = docs_path

    def schema_lookup(self, tables: list[str] | None = None) -> dict[str, Any]:
        return schema_lookup(self.recorder, db_path=self.db_path, tables=tables)

    def sql_query(self, query: str) -> dict[str, Any]:
        return sql_query(self.recorder, query, db_path=self.db_path)

    def rag_search(self, query: str, top_k: int = 3) -> dict[str, Any]:
        return rag_search(self.recorder, query, docs_path=self.docs_path, top_k=top_k)

    def document_lookup(self, doc_id: str) -> dict[str, Any]:
        return document_lookup(self.recorder, doc_id, docs_path=self.docs_path)
