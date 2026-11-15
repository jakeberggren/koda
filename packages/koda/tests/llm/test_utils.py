"""Tests for reading what a provider says when it answers with an error."""

import pytest

from koda.llm.utils import provider_message

UNSUPPORTED = "The 'gpt-5.5' model is not supported."


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"error": {"message": "Model not found.", "type": "invalid_request"}}, "Model not found."),
        ({"type": "error", "error": {"message": "Overloaded"}}, "Overloaded"),
        ({"message": "Bad request"}, "Bad request"),
        (
            {"detail": "The 'gpt-5.5' model is not supported."},
            "The 'gpt-5.5' model is not supported.",
        ),
        (f"{UNSUPPORTED}\n", UNSUPPORTED),
        ({"error": {"code": 500}}, None),
        ("   ", None),
        (None, None),
    ],
)
def test_the_providers_words_are_read_from_its_answer(body: object, message: str | None) -> None:
    assert provider_message(body) == message
