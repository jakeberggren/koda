import asyncio
from collections.abc import AsyncGenerator

from koda.providers.events import ProviderEvent, TextDelta
from koda_tui.backends import Backend

SAMPLE_RESPONSES = [
    "I'd be happy to help you with that! Let me think about the best approach here.",
    "You are absolutely right! Based on what you've described, I would suggest starting by breaking down the problem into smaller pieces.",  # noqa: E501
    "Here's what I found:\n\n1. First, you'll want to check the configuration\n2. Then verify the dependencies are installed\n3. Finally, run the tests to confirm everything works\n\nLet me know if you need more details!",  # noqa: E501
    "```python\ndef hello_world():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    hello_world()\n```\n\nThis should do the trick!",  # noqa: E501
]


class MockBackend(Backend):
    """A fake backend for testing the TUI without a real provider."""

    def __init__(
        self,
        responses: list[str] | None = None,
        chunk_size: int = 3,
        response_delay: float = 1.0,
        chunk_delay: float = 0.02,
    ) -> None:
        self._responses = responses or SAMPLE_RESPONSES
        self._response_index = 0
        self._chunk_size = chunk_size
        self._response_delay = response_delay
        self._chunk_delay = chunk_delay

    async def chat(self, message: str) -> AsyncGenerator[ProviderEvent]:
        """Stream back a fake response character by character."""
        await asyncio.sleep(self._response_delay)

        response = self._responses[self._response_index % len(self._responses)]
        self._response_index += 1

        for i in range(0, len(response), self._chunk_size):
            chunk = response[i : i + self._chunk_size]
            await asyncio.sleep(self._chunk_delay)
            yield TextDelta(text=chunk)
