"""The SignalBridge agent, built with Google ADK.

Four small agents run in order (a SequentialAgent conveyor belt):
    signal  ->  triage  ->  recovery  ->  governance

Each one is only allowed to call a few tools (see tools.py). The signal agent
uses the real free APIs (Open-Meteo weather, GDELT news). See docs/agents.md
and docs/external_api.md.

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
    news_scan_tool,
    supplier_options_tool,
    surplus_tool,
    weather_risk_tool,
)

signal_agent = LlmAgent(
    name="signal_agent",
    model=config.GEMINI_MODEL,
    description="Checks live weather and news for disruptions near a location.",
    instruction=prompts.SIGNAL,
    tools=[weather_risk_tool, news_scan_tool],
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

# The root agent is just the conveyor belt: run the four in order.
root_agent = SequentialAgent(
    name="signalbridge",
    description="Turns a disruption into an approved, traceable recovery plan.",
    sub_agents=[signal_agent, triage_agent, recovery_agent, governance_agent],
)
