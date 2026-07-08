"""Baseline demo agent with intentional, realistic mistakes."""

from __future__ import annotations

from agenteval.tools import Toolset


def run(task: dict, tools: Toolset) -> str:
    """Run a simple baseline policy for a benchmark task."""

    task_id = task["id"]
    if task["task_type"] == "sql_only":
        return _run_sql_task(task_id, tools)
    if task["task_type"] == "rag_only":
        return _run_rag_task(task_id, task["prompt"], tools)
    return _run_hybrid_task(task_id, tools)


def _run_sql_task(task_id: str, tools: Toolset) -> str:
    tools.schema_lookup()
    if task_id == "sql_declining_enterprise_revenue_q2":
        result = tools.sql_query(
            """
            SELECT c.customer_name, q1.revenue AS q1_revenue, q2.revenue AS q2_revenue
            FROM customers c
            JOIN invoices q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
            JOIN invoices q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
            WHERE q2.revenue < q1.revenue
            ORDER BY c.customer_name
            """
        )
        names = [row["customer_name"] for row in result["rows"]]
        return "Customers with declining revenue are: " + ", ".join(names) + "."
    if task_id == "sql_high_support_ticket_enterprise_q2":
        result = tools.sql_query(
            """
            SELECT c.customer_name, COUNT(*) AS ticket_count
            FROM customers c
            JOIN support_tickets t ON c.customer_id = t.customer_id
            WHERE c.segment = 'enterprise' AND t.quarter = '2026Q2'
            GROUP BY c.customer_name
            HAVING COUNT(*) > 20
            ORDER BY ticket_count DESC
            """
        )
        return _format_rows(result, "High-ticket enterprise customers")
    if task_id == "sql_usage_decline_enterprise_q2":
        result = tools.sql_query(
            """
            SELECT c.customer_name, q1.active_seats AS q1_seats, q2.active_seats AS q2_seats
            FROM customers c
            JOIN product_usage q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
            JOIN product_usage q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
            WHERE c.segment = 'enterprise' AND q2.active_seats < q1.active_seats
            ORDER BY c.customer_name
            """
        )
        return _format_rows(result, "Enterprise customers with active-seat decline")
    if task_id == "sql_upcoming_at_risk_renewals":
        result = tools.sql_query(
            """
            SELECT c.customer_name, r.renewal_date
            FROM customers c
            JOIN renewals r ON c.customer_id = r.customer_id
            WHERE r.renewal_status = 'at_risk'
            ORDER BY r.renewal_date
            """
        )
        return _format_rows(result, "At-risk renewals")
    if task_id == "sql_enterprise_arr_over_550k":
        result = tools.sql_query(
            """
            SELECT c.customer_name, s.arr
            FROM customers c
            JOIN subscriptions s ON c.customer_id = s.customer_id
            WHERE c.segment = 'enterprise' AND s.arr > 550000
            ORDER BY s.arr DESC
            """
        )
        return _format_rows(result, "Enterprise customers above 550000 ARR")
    return "I do not know how to answer this SQL task."


def _run_rag_task(task_id: str, prompt: str, tools: Toolset) -> str:
    search = tools.rag_search(prompt, top_k=2)
    docs = search["documents"]
    if task_id == "rag_enterprise_discount_policy":
        return "Discounts above 10 percent are automatically approved for enterprise renewals."
    if not docs:
        return "I could not find relevant document evidence."
    top = docs[0]
    return f"Based on {top['doc_id']}: {top['text']}"


def _run_hybrid_task(task_id: str, tools: Toolset) -> str:
    tools.schema_lookup()
    if task_id in {
        "hybrid_decline_and_renewal_risk",
        "hybrid_revenue_decline_without_churn_overclaim",
    }:
        result = tools.sql_query(
            """
            SELECT c.customer_name, q1.revenue AS q1_revenue, q2.revenue AS q2_revenue
            FROM customers c
            JOIN invoices q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
            JOIN invoices q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
            WHERE c.segment = 'enterprise' AND q2.revenue < q1.revenue
            ORDER BY c.customer_name
            """
        )
        names = [row["customer_name"] for row in result["rows"]]
        return (
            "Declining enterprise customers are "
            + ", ".join(names)
            + ". Acme Health has already churned, so all should be treated as renewal risks."
        )
    if task_id == "hybrid_usage_drop_and_support_context":
        # Wrong source choice: uses RAG only for a task that requires SQL and RAG.
        search = tools.rag_search("usage decline support context Acme OmniManufacturing", top_k=2)
        docs = search["documents"]
        return "The support context suggests risk: " + " ".join(doc["text"] for doc in docs)
    if task_id == "hybrid_high_tickets_and_policy_action":
        result = tools.sql_query(
            """
            SELECT c.customer_name, COUNT(*) AS ticket_count
            FROM customers c
            JOIN support_tickets t ON c.customer_id = t.customer_id
            WHERE c.segment = 'enterprise' AND t.quarter = '2026Q2'
            GROUP BY c.customer_name
            HAVING COUNT(*) > 20
            """
        )
        names = [row["customer_name"] for row in result["rows"]]
        return "Customers over the ticket threshold: " + ", ".join(names) + "."
    if task_id == "hybrid_discount_candidates_evidence":
        result = tools.sql_query(
            """
            SELECT c.customer_name, r.renewal_date
            FROM customers c
            JOIN renewals r ON c.customer_id = r.customer_id
            WHERE r.renewal_status = 'at_risk'
            """
        )
        names = [row["customer_name"] for row in result["rows"]]
        return "At-risk renewals are " + ", ".join(names) + ". Approved discounts can be offered."
    return "I do not know how to answer this hybrid task."


def _format_rows(result: dict, title: str) -> str:
    if not result["rows"]:
        return f"{title}: none found."
    parts = []
    for row in result["rows"]:
        facts = ", ".join(f"{key}={value}" for key, value in row.items() if key != "customer_name")
        parts.append(f"{row['customer_name']} ({facts})")
    return f"{title}: " + "; ".join(parts) + "."
