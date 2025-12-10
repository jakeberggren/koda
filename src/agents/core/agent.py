from collections.abc import AsyncIterator

from agents.core.message import AssistantMessage, Message, SystemMessage, UserMessage
from agents.observability import Observability
from agents.observability.decorators import observable
from agents.providers import Provider
from agents.utils.exceptions import ProviderValidationError


class Agent:
    def __init__(
        self,
        provider: Provider,
        system_message: str | None = None,
        observability: Observability | None = None,
    ) -> None:
        self.provider: Provider = provider
        self.system_message: str | None = system_message
        self.observability: Observability | None = observability
        self._history: list[Message] = []

        # Add system message to history if provided
        if system_message:
            self._history.append(SystemMessage(content=system_message))

    @observable(
        trace_name="agent.chat",
        log_generation=True,
    )
    async def chat(self, message: str) -> str:
        if not message or not message.strip():
            raise ProviderValidationError("Message cannot be empty")

        # Create user message and add to history
        user_message = UserMessage(content=message.strip())
        self._history.append(user_message)

        # Build message list for provider
        messages = self._build_messages()

        # Get response from provider
        response_text = await self.provider.chat(messages)

        # Create assistant message and add to history
        assistant_message = AssistantMessage(content=response_text)
        self._history.append(assistant_message)

        print(f"Observability type: {type(self.observability)}")

        return response_text

    @observable(trace_name="agent.stream")
    async def stream(self, message: str) -> AsyncIterator[str]:
        if not message or not message.strip():
            raise ProviderValidationError("Message cannot be empty")

        # Create user message and add to history
        user_message = UserMessage(content=message.strip())
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
        assistant_message = AssistantMessage(content=response_text)
        self._history.append(assistant_message)

    def add_message(self, message: Message) -> None:
        self._history.append(message)

    def get_history(self) -> list[Message]:
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

    def _build_messages(self) -> list[Message]:
        return self._history.copy()
