"""Messaging: messages between you and the agent. ``Conversation`` keeps what was said;
``Outbox`` sends what you write."""

from koda_tui.messaging.conversation import Conversation
from koda_tui.messaging.outbox import Outbox

__all__ = ["Conversation", "Outbox"]
