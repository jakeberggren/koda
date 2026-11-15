"""Tests for an Agent on its own: what it starts with."""

from __future__ import annotations

from typing import Any, cast

from koda.agent import Agent
from koda.sessions import Session


def test_an_agent_starts_with_a_new_session_and_no_tools() -> None:
    agent = Agent(cast("Any", object()))

    assert isinstance(agent.session, Session)
    assert agent.session.messages == []
    assert list(agent.tools) == []
    assert agent.instructions is None
