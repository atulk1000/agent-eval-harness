"""Agent registry for the CLI runner."""

from __future__ import annotations

from collections.abc import Callable

from agenteval.tools import Toolset

AgentFn = Callable[[dict, Toolset], str]


def get_agent(name: str) -> tuple[AgentFn, str]:
    if name == "baseline_agent":
        from agents.baseline_agent import run

        return run, "rule-baseline-v1"
    if name == "improved_agent":
        from agents.improved_agent import run

        return run, "rule-improved-v1"
    raise ValueError(f"Unknown agent '{name}'. Available: baseline_agent, improved_agent")
