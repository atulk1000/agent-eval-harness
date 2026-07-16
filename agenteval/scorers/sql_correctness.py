"""SQL execution and result correctness scorer."""

from __future__ import annotations

from typing import Any

from agenteval.scorers.common import row_entities, successful_events, tables_used


def score_sql_correctness(task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    expected = task.get("expected_sql", {})
    expected_entities = set(expected.get("expected_entities", []))
    unexpected_entities = set(expected.get("unexpected_entities", []))
    required_tables = {str(table).lower() for table in expected.get("required_tables", [])}
    labels: list[str] = []

    if not expected_entities and not required_tables:
        return {
            "score": 1.0,
            "applicable": False,
            "failure_labels": [],
            "missing_expected_rows": [],
            "unexpected_rows": [],
        }

    sql_events = [event for event in run.get("trace", []) if event.get("tool") == "sql_query"]
    successful_sql = successful_events(run, "sql_query")
    if not sql_events:
        return {
            "score": 0.0,
            "applicable": True,
            "failure_labels": ["missing_required_tool"],
            "missing_expected_rows": sorted(expected_entities),
            "unexpected_rows": [],
        }
    if not successful_sql:
        return {
            "score": 0.0,
            "applicable": True,
            "failure_labels": ["sql_execution_error"],
            "missing_expected_rows": sorted(expected_entities),
            "unexpected_rows": [],
        }

    found_entities = row_entities(run)
    missing = sorted(expected_entities - found_entities)
    unexpected = sorted(unexpected_entities & found_entities)
    used_tables = tables_used(run)
    missing_tables = sorted(required_tables - used_tables)

    if missing:
        labels.append("sql_missing_expected_row")
    if unexpected:
        labels.append("sql_false_positive_row")
    if missing_tables:
        labels.append("sql_missing_required_table")

    recall = (
        1.0
        if not expected_entities
        else len(expected_entities & found_entities) / len(expected_entities)
    )
    precision = 1.0
    relevant_found = found_entities & (expected_entities | unexpected_entities)
    if relevant_found:
        precision = len(expected_entities & found_entities) / len(relevant_found)
    table_score = (
        1.0 if not required_tables else len(required_tables & used_tables) / len(required_tables)
    )
    execution_score = 1.0
    score = execution_score * 0.25 + table_score * 0.20 + recall * 0.40 + precision * 0.15
    return {
        "score": round(score, 3),
        "applicable": True,
        "required_tables_used": sorted(required_tables & used_tables),
        "missing_required_tables": missing_tables,
        "found_entities": sorted(found_entities),
        "missing_expected_rows": missing,
        "unexpected_rows": unexpected,
        "failure_labels": labels,
    }
