"""Deterministic atomic factual-claim extraction."""

from __future__ import annotations

import re
from typing import Any, Protocol

from agenteval.claim_eval.cache import JudgeCache
from agenteval.claim_eval.models import SCHEMA_VERSION, claim_id, validate_claim
from agenteval.claim_eval.models import stable_id as make_stable_id

PROMPT_VERSION = "claim_extraction_v1"
VERB_HINTS = re.compile(
    r"\b(is|are|was|were|has|have|had|shows?|indicates?|requires?|must|declined?|"
    r"increased?|decreased?|opened?|churned?|approved?|supports?|caused?|faces?|faced|"
    r"emphasizes?|remains?|identifies?|points?|applies?|expanded?|praised?|asked?|connects?|"
    r"blocks?|affects?|should)\b",
    re.IGNORECASE,
)
NON_FACTUAL_STARTS = (
    "consider ",
    "recommend ",
    "review ",
    "please ",
    "next, ",
)


class DeterministicClaimExtractor:
    """Extract conservative claims without benchmark answers or oracle labels."""

    kind = "deterministic"

    def extract(self, run: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
        answer = str(run.get("final_answer", ""))
        run_id = str(run.get("run_id") or f"run_{task['id']}")
        candidates = _candidate_clauses(answer)
        claims: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source_text, text, start, end in candidates:
            normalized = _normalize(text)
            if not normalized or normalized in seen or not _is_factual(text):
                continue
            seen.add(normalized)
            ordinal = len(claims) + 1
            claim = {
                "schema_version": SCHEMA_VERSION,
                "claim_id": claim_id(str(task["id"]), ordinal, text),
                "run_id": run_id,
                "task_id": str(task["id"]),
                "ordinal": ordinal,
                "text": text.strip(),
                "source_text": source_text.strip(),
                "source_span": {"start": start, "end": end},
                "claim_type": _claim_type(text),
                "assertion_mode": _assertion_mode(text),
                "subject": _subject(text),
                "source_requirement": _source_requirement(text, task),
                "extractor": {
                    "kind": self.kind,
                    "provider": "local",
                    "model": "rules-v1",
                    "prompt_version": PROMPT_VERSION,
                },
                "extraction_warnings": [],
            }
            claims.append(validate_claim(claim))
        return claims


class SemanticExtractionProvider(Protocol):
    name: str
    model: str

    def extract(self, answer: str) -> list[dict[str, Any]]: ...


class CompositeClaimExtractor:
    """Merge deterministic claims with cached, validated semantic proposals."""

    def __init__(
        self,
        provider: SemanticExtractionProvider | None = None,
        *,
        cache: JudgeCache | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache or JudgeCache()

    def extract(self, run: dict[str, Any], task: dict[str, Any]) -> list[dict[str, Any]]:
        deterministic = DeterministicClaimExtractor().extract(run, task)
        if self.provider is None:
            return deterministic
        answer = str(run.get("final_answer", ""))
        key = make_stable_id(
            "extract",
            SCHEMA_VERSION,
            PROMPT_VERSION,
            self.provider.name,
            self.provider.model,
            answer,
            length=64,
        )
        cached = self.cache.get(key)
        try:
            proposals = (
                cached.get("claims", []) if cached is not None else self.provider.extract(answer)
            )
            if cached is None:
                self.cache.put(key, {"claims": proposals})
            semantic = self._records(
                proposals,
                run,
                task,
                answer,
                cache_hit=cached is not None,
            )
        except (TypeError, ValueError, KeyError, RuntimeError, TimeoutError) as exc:
            warning = f"semantic extraction fallback: {exc}"
            for claim in deterministic:
                claim["extraction_warnings"].append(warning)
            return deterministic
        merged = {_normalize(claim["text"]): claim for claim in deterministic}
        for claim in semantic:
            merged.setdefault(_normalize(claim["text"]), claim)
        ordered = sorted(
            merged.values(), key=lambda claim: (claim["source_span"]["start"], claim["text"])
        )
        for ordinal, claim in enumerate(ordered, start=1):
            claim["ordinal"] = ordinal
            claim["claim_id"] = claim_id(str(task["id"]), ordinal, claim["text"])
            validate_claim(claim)
        return ordered

    def _records(
        self,
        proposals: list[dict[str, Any]],
        run: dict[str, Any],
        task: dict[str, Any],
        answer: str,
        *,
        cache_hit: bool,
    ) -> list[dict[str, Any]]:
        if not isinstance(proposals, list):
            raise ValueError("semantic extraction output must be a list")
        records = []
        for index, proposal in enumerate(proposals, start=1):
            if not isinstance(proposal, dict) or not str(proposal.get("text", "")).strip():
                raise ValueError("semantic extraction claim must contain text")
            text = str(proposal["text"]).strip()
            source_text = str(proposal.get("source_text") or text)
            span = proposal.get("source_span")
            if not isinstance(span, dict):
                start = answer.lower().find(source_text.lower())
                start = max(start, 0)
                span = {"start": start, "end": start + len(source_text)}
            record = {
                "schema_version": SCHEMA_VERSION,
                "claim_id": claim_id(str(task["id"]), index, text),
                "run_id": str(run.get("run_id") or f"run_{task['id']}"),
                "task_id": str(task["id"]),
                "ordinal": index,
                "text": text,
                "source_text": source_text,
                "source_span": span,
                "claim_type": proposal.get("claim_type") or _claim_type(text),
                "assertion_mode": proposal.get("assertion_mode") or _assertion_mode(text),
                "subject": proposal.get("subject") or _subject(text),
                "source_requirement": proposal.get("source_requirement")
                or _source_requirement(text, task),
                "extractor": {
                    "kind": "semantic",
                    "provider": self.provider.name,
                    "model": self.provider.model,
                    "prompt_version": PROMPT_VERSION,
                    "cache_hit": cache_hit,
                },
                "extraction_warnings": [],
            }
            records.append(validate_claim(record))
        return records


def _candidate_clauses(answer: str) -> list[tuple[str, str, int, int]]:
    cleaned = _strip_markdown(answer)
    results: list[tuple[str, str, int, int]] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+|;\s+", cleaned):
        sentence = sentence.strip(" \t-*#")
        if not sentence:
            continue
        clauses = _split_compound(sentence)
        search_from = 0
        for clause in clauses:
            clause = clause.strip(" ,")
            if not clause:
                continue
            start = answer.lower().find(clause.lower(), search_from)
            if start < 0:
                start = max(0, cleaned.lower().find(clause.lower()))
            end = start + len(clause)
            results.append((sentence, clause, start, end))
            search_from = end
    return results


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(
        r"\*\*([^*]+)\*\*|__([^_]+)__",
        lambda match: match.group(1) or match.group(2),
        text,
    )
    text = text.replace("`", "").replace("*", "")
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-+]\s+|\d+[.)]\s+)", "", text)
    return text


def _split_compound(sentence: str) -> list[str]:
    parts = re.split(r",?\s+(?:and|but|so)\s+", sentence, flags=re.IGNORECASE)
    if len(parts) <= 1:
        return [sentence]
    if sum(bool(VERB_HINTS.search(part)) for part in parts) >= 2:
        return parts
    return [sentence]


def _is_factual(text: str) -> bool:
    lowered = text.strip().lower()
    if len(lowered.split()) < 2 or lowered.endswith(":"):
        return False
    if (
        lowered.startswith(NON_FACTUAL_STARTS)
        and "must" not in lowered
        and "required" not in lowered
    ):
        return False
    if " should " in f" {lowered} " and not any(
        term in lowered for term in ("policy", "requires", "required", "must")
    ):
        return False
    return bool(VERB_HINTS.search(text) or re.search(r"\d", text))


def _claim_type(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\d|%|percent|million|billion|\$", text):
        return "numeric"
    if any(term in lowered for term in ("because", "caused", "due to", "explains")):
        return "causal"
    if any(
        term in lowered for term in ("higher", "lower", "more than", "less than", "most", "least")
    ):
        return "comparative"
    if any(term in lowered for term in ("policy", "requires", "must", "approval", "contract")):
        return "policy_or_requirement"
    if any(
        term in lowered
        for term in ("churn", "at_risk", "at risk", "renewal", "approved", "terminated")
    ):
        return "business_status"
    if any(term in lowered for term in ("according to", "notes show", "data shows", "sql shows")):
        return "source_attribution"
    if _subject(text):
        return "entity_fact"
    return "descriptive"


def _assertion_mode(text: str) -> str:
    lowered = text.lower()
    if any(
        term in lowered
        for term in ("unclear", "unknown", "cannot determine", "not enough evidence")
    ):
        return "uncertain"
    if any(
        term in lowered
        for term in (
            "may",
            "might",
            "could",
            "suggests",
            "appears",
            "no evidence",
            "do not see evidence",
            "not confirmed",
            "does not show",
        )
    ):
        return "caveated"
    return "asserted"


def _subject(text: str) -> str | None:
    match = re.search(r"\b([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})\b", text)
    return match.group(1) if match else None


def _source_requirement(text: str, task: dict[str, Any]) -> str:
    lowered = text.lower()
    task_type = task.get("task_type")
    if task_type == "rag_only":
        return "rag"
    if task_type == "sql_only":
        return "sql"
    if any(
        term in lowered
        for term in ("policy", "contract", "account note", "support context", "notes show")
    ):
        return "rag"
    if re.search(
        r"\d|%|revenue|arr|tickets|active seats|declining|at-risk renewals?|at_risk renewals?",
        lowered,
    ):
        return "sql"
    return {"sql_only": "sql", "rag_only": "rag", "hybrid_sql_rag": "hybrid"}.get(task_type, "any")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
