"""The SignalBridge agent, built with Google ADK.

The automatic tick does not use this file. Weather, news, triage, the recovery
plan and the approval tier are plain Python (worker + domain/). This module is
only the optional conversational path: one agent that checks live weather and
news for a place.

Running this needs a Gemini API key (GOOGLE_API_KEY in .env). The rest of the
project (demo, tests, API read paths) runs without it.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent

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

# ADK looks for `root_agent`.
root_agent = signal_agent
