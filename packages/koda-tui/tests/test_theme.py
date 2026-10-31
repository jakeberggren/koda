import pytest
from prompt_toolkit.styles import Attrs
from pydantic import ValidationError
from rich.markdown import Markdown
from rich.text import Text

from koda_tui.appearance import THEMES, Appearance, RGBColor, Theme, Tokens, compose, rich
from koda_tui.settings import TuiSettings


def _attrs(setting: str, terminal_background: RGBColor | None, style: str) -> Attrs:
    appearance = Appearance(setting)
    appearance.terminal_background = terminal_background
    return appearance.style.get_attrs_for_style_str(style)


def test_auto_theme_derives_surface_from_dark_terminal_background() -> None:
    assert _attrs("auto", RGBColor(0, 0, 128), Tokens.Surface.RAISED).bgcolor == "202090"
    assert _attrs("auto", RGBColor(0, 0, 128), "class:pygments.keyword").color == "ansibrightblue"


def test_auto_theme_switches_to_light_theme_on_light_terminal_background() -> None:
    assert _attrs("auto", RGBColor(250, 250, 240), Tokens.Surface.RAISED).bgcolor == "dbdbd2"
    assert _attrs("auto", RGBColor(250, 250, 240), "class:pygments.keyword").color == "ansiblue"


def test_auto_theme_falls_back_to_dark_without_osc_11() -> None:
    assert _attrs("auto", None, Tokens.Surface.RAISED).bgcolor == "434343"


@pytest.mark.parametrize(
    ("setting", "terminal_background", "surface"),
    [
        ("terminal-dark", RGBColor(255, 255, 255), "434343"),
        ("terminal-light", RGBColor(0, 0, 0), "dcdcdc"),
        ("terminal-dark", RGBColor(0, 0, 128), "202090"),
    ],
)
def test_terminal_theme_derives_surface_only_from_matching_background(
    setting: str,
    terminal_background: RGBColor,
    surface: str,
) -> None:
    assert _attrs(setting, terminal_background, Tokens.Surface.RAISED).bgcolor == surface


def test_appearance_style_follows_theme_changes() -> None:
    appearance = Appearance("terminal-dark")
    appearance.theme = "terminal-light"

    assert appearance.style.get_attrs_for_style_str(Tokens.Surface.RAISED).bgcolor == "dcdcdc"


@pytest.mark.parametrize("value", ["auto", "terminal-dark", "terminal-light"])
def test_theme_setting_accepts_auto_and_registered_themes(value: str) -> None:
    assert TuiSettings(theme=value).theme == value


@pytest.mark.parametrize("value", ["solarized", "dark"])
def test_theme_setting_rejects_unknown_theme(value: str) -> None:
    with pytest.raises(ValidationError, match="Input should be one of 'auto', 'terminal-dark'"):
        TuiSettings(theme=value)


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
    assert _attrs("terminal-dark", None, "class:pygments.comment").dim
    assert not _attrs("terminal-dark", None, "class:pygments.comment.preproc").dim


def test_rich_and_prompt_toolkit_share_style_names() -> None:
    fragments = rich.render(Text("x", style=Tokens.Text.MUTED), width=10)

    assert list(fragments) == [(Tokens.Text.MUTED, "x")]


def test_rich_markdown_styles_render_as_style_names() -> None:
    fragments = rich.render(Markdown("`code`"), width=10)

    assert (Tokens.Code.INLINE, "code") in fragments


def test_rich_resolves_composed_tokens() -> None:
    muted_emphasis = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)
    fragments = rich.render(Text("x", style=muted_emphasis), width=10)

    assert list(fragments) == [(muted_emphasis, "x")]


def test_rgb_color_blends_toward_a_target() -> None:
    assert RGBColor(0, 0, 128).blend(RGBColor(255, 255, 255), 0.125) == RGBColor(32, 32, 144)
    assert RGBColor(32, 32, 144).hex == "#202090"


@pytest.mark.parametrize(
    ("color", "is_light"),
    [(RGBColor(0, 0, 0), False), (RGBColor(0, 0, 128), False), (RGBColor(250, 250, 240), True)],
)
def test_rgb_color_reads_as_light_or_dark(color: RGBColor, *, is_light: bool) -> None:
    assert color.is_light is is_light
