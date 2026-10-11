"""The resumed-history recap prints through rich Text (no Markdown), so entries are plain text cut at a word."""

from cli import recap_preview


def test_recap_preview_is_plain_and_cut_at_a_word():
    out = recap_preview("**Wo wir ging:** KermitStream / Tor-Integration fuer jrwl-messenger. "
                        "Letzte Sessions (9./10.10.): Design und Tests der Frame-Groessen", 70)
    assert "**" not in out and out.endswith("...")
    assert len(out) <= 71 and not out[:-1].endswith(" ")
    assert out.startswith("Wo wir ging:")


def test_recap_preview_short_text_is_untouched_apart_from_markup():
    assert recap_preview("# Title\n\nbody `code`", 100) == "Title\nbody code"
    assert recap_preview("", 10) == ""
