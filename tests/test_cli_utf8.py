"""Regression test: CLI must never crash on mis-decoded (surrogate) input.

A terminal that is not UTF-8 can deliver command-line / stdin bytes that
Python decodes into lone UTF-16 surrogates (e.g. "\\udcc3"). Printing such a
string to a strict UTF-8 stream raises UnicodeEncodeError. PAW sanitizes
these and reconfigures its output streams so the CLI degrades gracefully.
"""

from paw.cli import _sanitize_text


def test_sanitize_replaces_lone_surrogate():
    assert _sanitize_text("xin ch\udcc3ào") == "xin ch\ufffdào"


def test_sanitize_leaves_valid_text_untouched():
    text = "xin chào Đại ca — tiếng Việt UTF-8"
    assert _sanitize_text(text) == text


def test_sanitize_handles_empty_and_none_like():
    assert _sanitize_text("") == ""
    assert _sanitize_text("plain ascii") == "plain ascii"


def test_sanitize_replaces_multiple_surrogates():
    assert _sanitize_text("a\udcc3b\udcffc") == "a\ufffdb\ufffdc"
