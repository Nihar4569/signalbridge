"""The SignalBridge agent, built with Google ADK.

The automatic tick does not use this file. Weather, news, triage, and the
recovery plan are plain Python (worker + domain/). This module is only the
optional conversational path.

Triage and recovery used to be LLM agents on every tick. They are retired:
domain/triage.py and domain/planner.py do that work. Governance stays here
until the manager report (domain/report.py) replaces it.

Running this needs a Gemini API key (GOOGLE_API_KEY in .env). The rest of the
project (demo, tests, API read paths) runs without it.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent

from ..core import config
from . import prompts
from .tools import news_scan_tool, weather_risk_tool

signal_agent = LlmAgent(
    name="signal_agent",
    model=config.GEMINI_MODEL,
    description="Checks live weather and news for disruptions near a location.",
    instruction=prompts.SIGNAL,
    tools=[weather_risk_tool, news_scan_tool],
)

governance_agent = LlmAgent(
    name="governance_agent",
    model=config.GEMINI_MODEL,
    description="Routes the plan to the correct human approver.",
    instruction=prompts.GOVERNANCE,
    tools=[],
)

# Signal check, then who must approve. Triage and recovery are not on this belt.
root_agent = SequentialAgent(
    name="signalbridge",
    description="Checks live signals, then routes a plan to a human approver.",
    sub_agents=[signal_agent, governance_agent],
)
