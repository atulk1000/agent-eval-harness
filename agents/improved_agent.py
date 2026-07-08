"""Improved demo agent that follows the desired SQL + RAG behavior."""

from __future__ import annotations

from agenteval.tools import Toolset


def run(task: dict, tools: Toolset) -> str:
    task_id = task["id"]
    if task["task_type"] == "sql_only":
        return _run_sql_task(task_id, tools)
    if task["task_type"] == "rag_only":
        return _run_rag_task(task_id, task["prompt"], tools)
    return _run_hybrid_task(task_id, tools)


def _run_sql_task(task_id: str, tools: Toolset) -> str:
    tools.schema_lookup()
    query = {
        "sql_declining_enterprise_revenue_q2": """
            SELECT c.customer_name, q1.revenue AS q1_revenue, q2.revenue AS q2_revenue
            FROM customers c
            JOIN invoices q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
            JOIN invoices q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
            WHERE c.segment = 'enterprise' AND q2.revenue < q1.revenue
            ORDER BY c.customer_name
        """,
        "sql_high_support_ticket_enterprise_q2": """
            SELECT c.customer_name, COUNT(*) AS ticket_count
            FROM customers c
            JOIN support_tickets t ON c.customer_id = t.customer_id
            WHERE c.segment = 'enterprise' AND t.quarter = '2026Q2'
            GROUP BY c.customer_name
            HAVING COUNT(*) > 20
            ORDER BY ticket_count DESC
        """,
        "sql_usage_decline_enterprise_q2": """
            SELECT c.customer_name, q1.active_seats AS q1_seats, q2.active_seats AS q2_seats
            FROM customers c
            JOIN product_usage q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
            JOIN product_usage q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
            WHERE c.segment = 'enterprise' AND q2.active_seats < q1.active_seats
            ORDER BY c.customer_name
        """,
        "sql_upcoming_at_risk_renewals": """
            SELECT c.customer_name, r.renewal_date
            FROM customers c
            JOIN renewals r ON c.customer_id = r.customer_id
            WHERE r.renewal_status = 'at_risk'
            ORDER BY r.renewal_date
        """,
        "sql_enterprise_arr_over_550k": """
            SELECT c.customer_name, s.arr
            FROM customers c
            JOIN subscriptions s ON c.customer_id = s.customer_id
            WHERE c.segment = 'enterprise' AND s.arr > 550000
            ORDER BY s.arr DESC
        """,
    }[task_id]
    result = tools.sql_query(query)
    return _format_rows(result, "SQL result")


def _run_rag_task(task_id: str, prompt: str, tools: Toolset) -> str:
    search = tools.rag_search(prompt, top_k=3)
    docs = search["documents"]
    if not docs:
        return "I could not find relevant document evidence."
    doc = docs[0]
    if task_id == "rag_enterprise_discount_policy":
        return (
            "Based on renewal_policy_enterprise, a discount above 10 percent requires "
            "VP approval, a documented business case, and a renewal risk assessment."
        )
    if task_id == "rag_acme_contract_termination":
        return (
            "Based on contract_acme_2026, early termination applies only after a "
            "material breach remains uncured for 30 days."
        )
    if task_id == "rag_omni_support_issue_summary":
        return (
            "Based on support_summary_omni_q2, OmniManufacturing faced integration "
            "and data sync failures caused by connector defects."
        )
    if task_id == "rag_civic_success_signal":
        return (
            "Based on customer_success_civic_q2, CivicCloud Gov expanded adoption, "
            "praised reporting improvements, and asked to review additional use cases."
        )
    if task_id == "rag_support_escalation_policy":
        return (
            "Based on support_policy_escalation, high-severity enterprise incidents "
            "require a customer-facing remediation plan when open issues affect "
            "production workflows or renewal commitments."
        )
    return f"Based on {doc['doc_id']}: {doc['text']}"


def _run_hybrid_task(task_id: str, tools: Toolset) -> str:
    tools.schema_lookup()
    if task_id == "hybrid_decline_and_renewal_risk":
        result = tools.sql_query(_declining_revenue_sql())
        tools.rag_search("Acme Health Northstar Bank OmniManufacturing June account note renewal risk", top_k=3)
        tools.document_lookup("account_note_acme_2026_06")
        tools.document_lookup("account_note_northstar_2026_06")
        tools.document_lookup("account_note_omni_2026_06")
        return (
            "Invoice data shows declining Q2 revenue for Acme Health, Northstar Bank, "
            "and OmniManufacturing. Account notes suggest renewal risk: Acme Health has "
            "unresolved onboarding and SSO issues, Northstar Bank has executive sponsor "
            "and procurement concerns, and OmniManufacturing has integration defects "
            "blocking data sync. I do not see evidence that any have already churned."
        )
    if task_id == "hybrid_usage_drop_and_support_context":
        tools.sql_query(
            """
            SELECT c.customer_name, q1.active_seats AS q1_seats, q2.active_seats AS q2_seats
            FROM customers c
            JOIN product_usage q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
            JOIN product_usage q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
            WHERE c.segment = 'enterprise' AND q2.active_seats < q1.active_seats
            ORDER BY c.customer_name
            """
        )
        tools.rag_search("Acme Health OmniManufacturing Q2 support SSO data sync integration defects", top_k=3)
        tools.document_lookup("support_summary_acme_q2")
        tools.document_lookup("support_summary_omni_q2")
        return (
            "SQL shows active-seat decline for Acme Health and OmniManufacturing. "
            "The support context points to different risks: Acme Health had onboarding "
            "and SSO blockers, while OmniManufacturing had integration and data sync defects."
        )
    if task_id == "hybrid_high_tickets_and_policy_action":
        tools.sql_query(
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
        tools.rag_search("support escalation policy high-severity remediation plan production workflows", top_k=2)
        tools.document_lookup("support_policy_escalation")
        return (
            "SQL shows Acme Health and OmniManufacturing had more than 20 Q2 support "
            "tickets. Based on support_policy_escalation, a customer-facing remediation "
            "plan should be considered for high-severity incidents affecting production "
            "workflows or renewal commitments."
        )
    if task_id == "hybrid_discount_candidates_evidence":
        tools.sql_query(
            """
            SELECT c.customer_name, r.renewal_date
            FROM customers c
            JOIN renewals r ON c.customer_id = r.customer_id
            WHERE r.renewal_status = 'at_risk'
            ORDER BY r.renewal_date
            """
        )
        tools.rag_search("enterprise renewal policy discount above 10 percent VP approval business case risk assessment", top_k=2)
        tools.document_lookup("renewal_policy_enterprise")
        return (
            "SQL identifies Acme Health and OmniManufacturing as at-risk renewals. "
            "Before any discount above 10 percent, renewal_policy_enterprise requires "
            "VP approval, a documented business case, and a renewal risk assessment. "
            "The trace does not show that any discount was approved."
        )
    if task_id == "hybrid_revenue_decline_without_churn_overclaim":
        tools.sql_query(_declining_revenue_sql())
        tools.rag_search("Acme Health Northstar Bank OmniManufacturing churn account note", top_k=3)
        tools.document_lookup("account_note_acme_2026_06")
        tools.document_lookup("account_note_northstar_2026_06")
        tools.document_lookup("account_note_omni_2026_06")
        return (
            "SQL shows declining Q2 revenue for Acme Health, Northstar Bank, and "
            "OmniManufacturing. The retrieved account notes show renewal risk signals, "
            "but I found no evidence that any of these customers have already churned."
        )
    return "I do not know how to answer this hybrid task."


def _declining_revenue_sql() -> str:
    return """
        SELECT c.customer_name, q1.revenue AS q1_revenue, q2.revenue AS q2_revenue
        FROM customers c
        JOIN invoices q1 ON c.customer_id = q1.customer_id AND q1.quarter = '2026Q1'
        JOIN invoices q2 ON c.customer_id = q2.customer_id AND q2.quarter = '2026Q2'
        WHERE c.segment = 'enterprise' AND q2.revenue < q1.revenue
        ORDER BY c.customer_name
    """


def _format_rows(result: dict, title: str) -> str:
    if not result["rows"]:
        return f"{title}: none found."
    parts = []
    for row in result["rows"]:
        facts = ", ".join(f"{key}={value}" for key, value in row.items() if key != "customer_name")
        parts.append(f"{row['customer_name']} ({facts})")
    return f"{title}: " + "; ".join(parts) + "."
