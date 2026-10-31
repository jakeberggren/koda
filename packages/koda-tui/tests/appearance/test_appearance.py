"""Tests for the stylesheet: it follows the theme, and every token has a rule."""

import pytest

from koda_tui.appearance import THEMES, Appearance, Theme, Tokens


def test_appearance_style_follows_theme_changes() -> None:
    appearance = Appearance("terminal-dark")
    appearance.theme = "terminal-light"

    assert appearance.style.get_attrs_for_style_str(Tokens.Surface.RAISED).bgcolor == "dcdcdc"


@pytest.mark.parametrize(
    "theme",
    [theme for theme in THEMES.values() if isinstance(theme, Theme)],
    ids=lambda theme: theme.name,
)
def test_stylesheet_applies_every_theme_rule(theme: Theme) -> None:
    applied = dict(Appearance(theme.name).style.style_rules)

    for name, rule in theme.rules.items():
        assert applied[name.removeprefix("class:")] == rule


def _tokens(namespace: type = Tokens) -> list[str]:
    tokens: list[str] = []
    for value in vars(namespace).values():
        if isinstance(value, str) and value.startswith("class:"):
            tokens.append(value)
        elif isinstance(value, type):
            tokens.extend(_tokens(value))
    return tokens


@pytest.mark.parametrize("theme", THEMES)
def test_every_token_has_a_rule(theme: str) -> None:
    rules = {name for name, _ in Appearance(theme).style.style_rules}

    assert {token.removeprefix("class:") for token in _tokens()} <= rules


def test_syntax_child_classes_reset_inherited_dim() -> None:
    style = Appearance("terminal-dark").style
    assert style.get_attrs_for_style_str("class:pygments.comment").dim
    assert not style.get_attrs_for_style_str("class:pygments.comment.preproc").dim
