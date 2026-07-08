"""Demo database and document corpus setup."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "sqlite" / "customer_risk.db"
DEFAULT_DOCS_PATH = ROOT / "data" / "docs" / "documents.json"


def ensure_demo_data(
    db_path: str | Path = DEFAULT_DB_PATH,
    docs_path: str | Path = DEFAULT_DOCS_PATH,
) -> tuple[Path, Path]:
    """Create the local demo database and document corpus if needed."""

    db = Path(db_path)
    docs = Path(docs_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    docs.parent.mkdir(parents=True, exist_ok=True)
    seed_database(db)
    seed_documents(docs)
    return db, docs


def seed_database(db_path: str | Path) -> None:
    """Seed a deterministic SQLite database for the demo domain."""

    db = Path(db_path)
    with closing(sqlite3.connect(db)) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS customers;
            DROP TABLE IF EXISTS invoices;
            DROP TABLE IF EXISTS subscriptions;
            DROP TABLE IF EXISTS product_usage;
            DROP TABLE IF EXISTS support_tickets;
            DROP TABLE IF EXISTS renewals;

            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL,
                segment TEXT NOT NULL,
                industry TEXT NOT NULL,
                region TEXT NOT NULL
            );

            CREATE TABLE invoices (
                invoice_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                quarter TEXT NOT NULL,
                revenue INTEGER NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE subscriptions (
                subscription_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                arr INTEGER NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE product_usage (
                usage_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                quarter TEXT NOT NULL,
                active_seats INTEGER NOT NULL,
                api_calls INTEGER NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE support_tickets (
                ticket_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                quarter TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );

            CREATE TABLE renewals (
                renewal_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                renewal_date TEXT NOT NULL,
                renewal_status TEXT NOT NULL,
                owner TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            );
            """
        )

        customers = [
            (1, "Acme Health", "enterprise", "healthcare", "NA"),
            (2, "Northstar Bank", "enterprise", "financial services", "NA"),
            (3, "BrightCart Retail", "midmarket", "retail", "NA"),
            (4, "CivicCloud Gov", "enterprise", "public sector", "NA"),
            (5, "DataForge Labs", "startup", "technology", "EU"),
            (6, "OmniManufacturing", "enterprise", "manufacturing", "NA"),
        ]
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)

        invoices = [
            (1, 1, "2026Q1", 120000),
            (2, 1, "2026Q2", 90000),
            (3, 2, "2026Q1", 220000),
            (4, 2, "2026Q2", 180000),
            (5, 3, "2026Q1", 45000),
            (6, 3, "2026Q2", 55000),
            (7, 4, "2026Q1", 150000),
            (8, 4, "2026Q2", 160000),
            (9, 5, "2026Q1", 30000),
            (10, 5, "2026Q2", 28000),
            (11, 6, "2026Q1", 140000),
            (12, 6, "2026Q2", 100000),
        ]
        conn.executemany("INSERT INTO invoices VALUES (?, ?, ?, ?)", invoices)

        subscriptions = [
            (1, 1, "Enterprise", 480000, "active"),
            (2, 2, "Enterprise Plus", 880000, "active"),
            (3, 3, "Growth", 180000, "active"),
            (4, 4, "Enterprise", 600000, "active"),
            (5, 5, "Starter", 90000, "active"),
            (6, 6, "Enterprise", 560000, "active"),
        ]
        conn.executemany("INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?)", subscriptions)

        usage = [
            (1, 1, "2026Q1", 520, 1250000),
            (2, 1, "2026Q2", 410, 900000),
            (3, 2, "2026Q1", 780, 2400000),
            (4, 2, "2026Q2", 820, 2550000),
            (5, 3, "2026Q1", 120, 220000),
            (6, 3, "2026Q2", 150, 300000),
            (7, 4, "2026Q1", 310, 980000),
            (8, 4, "2026Q2", 330, 1020000),
            (9, 5, "2026Q1", 44, 80000),
            (10, 5, "2026Q2", 39, 76000),
            (11, 6, "2026Q1", 430, 1100000),
            (12, 6, "2026Q2", 260, 650000),
        ]
        conn.executemany("INSERT INTO product_usage VALUES (?, ?, ?, ?, ?)", usage)

        tickets = []
        ticket_id = 1
        ticket_counts = {
            1: [("high", "onboarding", 8), ("medium", "sso", 12), ("low", "training", 8)],
            2: [("medium", "procurement", 4), ("low", "analytics", 8)],
            3: [("low", "catalog", 9)],
            4: [("low", "reporting", 4)],
            5: [("medium", "api", 6)],
            6: [("high", "integration", 14), ("medium", "data_sync", 20)],
        }
        for customer_id, groups in ticket_counts.items():
            for severity, category, count in groups:
                for _ in range(count):
                    tickets.append((ticket_id, customer_id, "2026Q2", severity, category, "closed"))
                    ticket_id += 1
        conn.executemany("INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?)", tickets)

        renewals = [
            (1, 1, "2026-08-31", "at_risk", "Maya Chen"),
            (2, 2, "2026-09-15", "monitor", "Leo Singh"),
            (3, 3, "2026-11-30", "healthy", "Iris Bell"),
            (4, 4, "2027-01-15", "healthy", "Maya Chen"),
            (5, 5, "2026-10-01", "monitor", "Nina Ortiz"),
            (6, 6, "2026-07-31", "at_risk", "Leo Singh"),
        ]
        conn.executemany("INSERT INTO renewals VALUES (?, ?, ?, ?, ?)", renewals)
        conn.commit()


def seed_documents(docs_path: str | Path) -> None:
    """Write the deterministic demo document corpus."""

    docs = [
        {
            "doc_id": "account_note_acme_2026_06",
            "title": "Acme Health June Account Note",
            "customer": "Acme Health",
            "doc_type": "account_note",
            "text": (
                "Acme Health still has unresolved onboarding issues before the August "
                "renewal. The executive sponsor requested a clear adoption plan and "
                "SSO remediation timeline. The note does not say that Acme has churned."
            ),
        },
        {
            "doc_id": "account_note_northstar_2026_06",
            "title": "Northstar Bank June Account Note",
            "customer": "Northstar Bank",
            "doc_type": "account_note",
            "text": (
                "Northstar Bank changed executive sponsors in June. Procurement is "
                "concerned about seat expansion, and the new sponsor wants proof of "
                "analytics adoption before renewal. No discount request has been approved."
            ),
        },
        {
            "doc_id": "account_note_omni_2026_06",
            "title": "OmniManufacturing June Account Note",
            "customer": "OmniManufacturing",
            "doc_type": "account_note",
            "text": (
                "OmniManufacturing's plant rollout is delayed because integration defects "
                "blocked data sync. The customer champion escalated renewal risk and asked "
                "for a remediation plan before the July renewal."
            ),
        },
        {
            "doc_id": "renewal_policy_enterprise",
            "title": "Enterprise Renewal Policy",
            "customer": None,
            "doc_type": "policy",
            "text": (
                "Enterprise renewal discounts above 10 percent require VP approval, a "
                "documented business case, and a renewal risk assessment. Customer success "
                "must record evidence before approval."
            ),
        },
        {
            "doc_id": "contract_acme_2026",
            "title": "Acme Health Contract Excerpt",
            "customer": "Acme Health",
            "doc_type": "contract",
            "text": (
                "Acme Health has a 99.9 percent SLA clause. Early termination applies only "
                "after a material breach remains uncured for 30 days."
            ),
        },
        {
            "doc_id": "support_summary_acme_q2",
            "title": "Acme Health Q2 Support Summary",
            "customer": "Acme Health",
            "doc_type": "support_summary",
            "text": (
                "Acme Health opened repeated onboarding and SSO tickets in Q2. Most tickets "
                "were resolved, but rollout blockers remain for two departments."
            ),
        },
        {
            "doc_id": "support_summary_omni_q2",
            "title": "OmniManufacturing Q2 Support Summary",
            "customer": "OmniManufacturing",
            "doc_type": "support_summary",
            "text": (
                "OmniManufacturing opened high-severity tickets about integration and data "
                "sync failures. Engineering identified connector defects as the main issue."
            ),
        },
        {
            "doc_id": "customer_success_civic_q2",
            "title": "CivicCloud Gov Q2 Success Note",
            "customer": "CivicCloud Gov",
            "doc_type": "customer_success_note",
            "text": (
                "CivicCloud Gov expanded adoption in Q2. The sponsor praised reporting "
                "improvements and asked to review additional use cases next quarter."
            ),
        },
        {
            "doc_id": "contract_northstar_2026",
            "title": "Northstar Bank Contract Excerpt",
            "customer": "Northstar Bank",
            "doc_type": "contract",
            "text": (
                "Northstar Bank's contract allows annual seat true-up at renewal. Pricing "
                "changes require procurement review but do not automatically trigger discounts."
            ),
        },
        {
            "doc_id": "support_policy_escalation",
            "title": "Support Escalation Policy",
            "customer": None,
            "doc_type": "policy",
            "text": (
                "High-severity enterprise incidents require a customer-facing remediation "
                "plan when open issues affect production workflows or renewal commitments."
            ),
        },
    ]
    Path(docs_path).write_text(json.dumps(docs, indent=2, sort_keys=True), encoding="utf-8")


def load_documents(docs_path: str | Path = DEFAULT_DOCS_PATH) -> list[dict[str, Any]]:
    return json.loads(Path(docs_path).read_text(encoding="utf-8"))
