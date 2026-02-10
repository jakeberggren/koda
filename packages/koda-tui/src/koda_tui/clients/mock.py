import asyncio
from collections.abc import AsyncGenerator

from koda.providers.events import ProviderEvent, TextDelta
from koda_tui.clients import Client

SAMPLE_RESPONSES = [
    """Here's the diff for the changes I made:

```diff
--- a/src/config.py
+++ b/src/config.py
@@ -12,8 +12,15 @@ class Config:
     def __init__(self, path: str = None):
         self.path = path or DEFAULT_CONFIG_PATH
         self._data = {}
+        self._cache = {}
+        self._initialized = False

     def load(self) -> dict:
-        with open(self.path) as f:
-            return json.load(f)
+        if self._initialized and self.path in self._cache:
+            return self._cache[self.path]
+
+        with open(self.path, encoding='utf-8') as f:
+            self._data = json.load(f)
+            self._cache[self.path] = self._data
+            self._initialized = True
+        return self._data
```

This adds caching to prevent repeated file reads.""",
    "I'd be happy to help you with that! Let me think about the best approach here.",
    "You are absolutely right! Based on what you've described, I would suggest starting by breaking down the problem into smaller pieces.",  # noqa: E501
    "Here's what I found:\n\n1. First, you'll want to check the configuration\n2. Then verify the dependencies are installed\n3. Finally, run the tests to confirm everything works\n\nLet me know if you need more details!",  # noqa: E501
    "```python\ndef hello_world():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    hello_world()\n```\n\nThis should do the trick!",  # noqa: E501
]


class MockClient(Client):
    """A fake client for testing the TUI without a real provider."""

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

    def reconfigure(self) -> None:
        """No-op for mock client."""

    async def chat(self, message: str) -> AsyncGenerator[ProviderEvent]:  # noqa: ARG002 - unused argument
        """Stream back a fake response character by character."""
        await asyncio.sleep(self._response_delay)

        response = self._responses[self._response_index % len(self._responses)]
        self._response_index += 1

        for i in range(0, len(response), self._chunk_size):
            chunk = response[i : i + self._chunk_size]
            await asyncio.sleep(self._chunk_delay)
            yield TextDelta(text=chunk)
