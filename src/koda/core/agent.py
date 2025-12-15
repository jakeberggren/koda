from collections.abc import AsyncIterator

from langfuse import observe

from koda import providers
from koda.core import message
from koda.utils import exceptions


class Agent:
    def __init__(
        self,
        provider: providers.Provider,
        system_message: str | None = None,
    ) -> None:
        self.provider: providers.Provider = provider
        self.system_message: str | None = system_message
        self._history: list[message.Message] = []

        if system_message:
            self._history.append(message.SystemMessage(content=system_message))

    @observe(name="agent.chat", as_type="agent")
    async def chat(self, user_text: str) -> str:
        if not user_text or not user_text.strip():
            raise exceptions.ProviderValidationError("Message cannot be empty")

        # Create user message and add to history
        user_message = message.UserMessage(content=user_text.strip())
        self._history.append(user_message)

        # Build message list for provider
        messages = self._build_messages()

        # Get response from provider
        response_text = await self.provider.chat(messages)

        # Create assistant message and add to history
        assistant_message = message.AssistantMessage(content=response_text)
        self._history.append(assistant_message)

        return response_text

    @observe(name="agent.stream", as_type="agent")
    async def stream(self, user_text: str) -> AsyncIterator[str]:
        if not user_text or not user_text.strip():
            raise exceptions.ProviderValidationError("Message cannot be empty")

        # Create user message and add to history
        user_message = message.UserMessage(content=user_text.strip())
        self._history.append(user_message)

        # Build message list for provider
        messages = self._build_messages()

        # Stream response from provider
        stream = self.provider.stream(messages)
        response_chunks: list[str] = []
        async for chunk in stream:
            response_chunks.append(chunk)
            yield chunk

        # Create assistant message and add to history
        response_text = "".join(response_chunks)
        assistant_message = message.AssistantMessage(content=response_text)
        self._history.append(assistant_message)

    def add_message(self, message_to_add: message.Message) -> None:
        self._history.append(message_to_add)

    def get_history(self) -> list[message.Message]:
        return self._history.copy()

    def clear_history(self) -> None:
        # Preserve system message if it exists
        system_msg = None
        if self._history and self._history[0].role.value == "system":
            system_msg = self._history[0]

        self._history.clear()

        # Restore system message if it existed
        if system_msg:
            self._history.append(system_msg)

    def reset(self) -> None:
        self.clear_history()

        # Reset provider state if it has a reset_state method
        reset_state = getattr(self.provider, "reset_state", None)
        if reset_state is not None and callable(reset_state):
            reset_state()

    def _build_messages(self) -> list[message.Message]:
        return self._history.copy()
