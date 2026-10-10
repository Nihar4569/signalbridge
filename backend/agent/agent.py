"""The SignalBridge agent, built with Google ADK.

Three small agents run in order (a SequentialAgent conveyor belt):
    triage  ->  recovery  ->  governance

Each one is only allowed to call a few tools (see tools.py). See docs/agents.md
for the plain-English explanation.

Running this needs a Gemini API key (GOOGLE_API_KEY in .env). The rest of the
project (demo, tests, API read paths) runs without it.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent

from ..core import config
from . import prompts
from .tools import (
    exposure_tool,
    internal_balance_tool,
    margin_tool,
    supplier_options_tool,
    surplus_tool,
)

triage_agent = LlmAgent(
    name="triage_agent",
    model=config.GEMINI_MODEL,
    description="Decides whether a disruption actually threatens an order.",
    instruction=prompts.TRIAGE,
    tools=[exposure_tool],
)

recovery_agent = LlmAgent(
    name="recovery_agent",
    model=config.GEMINI_MODEL,
    description="Builds the best recovery plan for an at-risk order.",
    instruction=prompts.RECOVERY,
    tools=[internal_balance_tool, supplier_options_tool, margin_tool, surplus_tool],
)

governance_agent = LlmAgent(
    name="governance_agent",
    model=config.GEMINI_MODEL,
    description="Routes the plan to the correct human approver.",
    instruction=prompts.GOVERNANCE,
    tools=[],
)

# The root agent is just the conveyor belt: run the three in order.
root_agent = SequentialAgent(
    name="signalbridge",
    description="Turns a disruption into an approved, traceable recovery plan.",
    sub_agents=[triage_agent, recovery_agent, governance_agent],
)
