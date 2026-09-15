"""Inline telex-to-Vietnamese converter for TUI input.

Bypasses the terminal's IME entirely -- converts ASCII telex keystrokes
to Vietnamese Unicode.  Enable in the TUI with ``/telex on`` or
``--telex`` CLI flag.

Telex rules (simplified VTV layout):
  Doubles:  oo->ô  ee->ê  ow->ơ  uw->ư  aa->â  dd->đ
  Tones:    s->huyền  f->hỏi  r->ngã  x->sắc  j->không thanh

  Heuristic: a tone key between two vowels is always a tone mark
  (e.g. ``chaso``->``chào``), except ``j`` which needs telex_mode
  (avoids mangling English words like ``project``).
  A tone key at end-of-token requires has_doubles or telex_mode.
  A tone key followed by consonants (e.g. ``world``) is never a
  tone mark -- this pattern is common in English.

Example:
    >>> convert_telems("tooi")
    'tôi'
    >>> convert_telems("chaso")
    'chào'
"""

from __future__ import annotations

import re

_DOUBLES: dict[str, str] = {
    "oo": "ô",
    "ee": "ê",
    "ow": "ơ",
    "uw": "ư",
    "aa": "â",
    "dd": "đ",
}

_TONE_KEYS = frozenset({"s", "f", "r", "x", "j"})
_TONE_ORDER = ("s", "f", "r", "x")  # huyền, hỏi, ngã, sắc

# Vowel -> tone-marked variants (index matches _TONE_ORDER) + plain form at end
_VOWEL_TONES: dict[str, str] = {
    "a":  "àảãáa",
    "â":  "ầẩẫấâ",
    "e":  "èẻẽée",
    "ê":  "ềểễếê",
    "i":  "ìỉĩíi",
    "o":  "òỏõóo",
    "ô":  "ồổỗốô",
    "ơ":  "ờởỡớơ",
    "u":  "ùủũúu",
    "ư":  "ừửữứư",
    "y":  "ỳỷỹýy",
}
_TONEABLE = frozenset(_VOWEL_TONES.keys())


def _find_toneable(chars: list[str], start: int) -> int:
    """Nearest toneable vowel at or before *start*."""
    for i in range(start, -1, -1):
        if chars[i].lower() in _TONEABLE:
            return i
    return -1


def _apply_tone(vowel: str, tone_key: str) -> str:
    """Apply a tone mark to *vowel*, preserving case."""
    lower = vowel.lower()
    if lower not in _VOWEL_TONES:
        return vowel
    if tone_key == "j":  # không thanh -> unmarked
        return vowel.upper() if vowel.isupper() else lower
    tone_idx = _TONE_ORDER.index(tone_key)
    result = _VOWEL_TONES[lower][tone_idx]
    return result.upper() if vowel.isupper() else result


def _process_doubles(chars: list[str]) -> list[str]:
    result: list[str] = []
    i = 0
    while i < len(chars):
        if i + 1 < len(chars) and (chars[i] + chars[i + 1]) in _DOUBLES:
            result.append(_DOUBLES[chars[i] + chars[i + 1]])
            i += 2
        else:
            result.append(chars[i])
            i += 1
    return result


def _has_doubles(chars: list[str]) -> bool:
    i = 0
    while i + 1 < len(chars):
        if chars[i] + chars[i + 1] in _DOUBLES:
            return True
        i += 1
    return False


def _next_is_vowel(chars: list[str], pos: int) -> bool:
    """Is there a toneable vowel immediately after *pos*."""
    if pos + 1 < len(chars):
        return chars[pos + 1].lower() in _TONEABLE
    return False


def _process_tones(
    chars: list[str],
    *,
    telex_mode: bool = False,
    has_doubles: bool = False,
) -> list[str]:
    """Apply tone marks based on context heuristics.

    Rules:
    1. Tone key between two vowels (``chaso``->``chào``): apply,
       except ``j`` which needs telex_mode (avoids ``project``).
    2. Tone key at end of token (``chax``->``chá``) with has_doubles
       or telex_mode: apply.
    3. Tone key followed by consonants (``world``): never apply.
    """
    result = list(chars)
    i = len(result) - 1
    while i >= 0:
        c = result[i]
        if c in _TONE_KEYS:
            vidx = _find_toneable(result, i - 1)
            if vidx < 0:
                i -= 1
                continue
            follows_vowel = _next_is_vowel(result, i)
            at_end = i == len(result) - 1

            if follows_vowel:
                # 'j' between vowels is ambiguous (project) -> needs toggle
                if c != "j" or telex_mode:
                    result[vidx] = _apply_tone(result[vidx], c)
                    result.pop(i)
                    i -= 1
                    continue
            elif at_end and (has_doubles or telex_mode):
                result[vidx] = _apply_tone(result[vidx], c)
                result.pop(i)
                i -= 1
                continue
        i -= 1
    return result


def _process_token(token: str, *, telex_mode: bool = False) -> str:
    if not token:
        return token
    chars = [c.lower() for c in token]
    has_doubles = _has_doubles(chars)
    chars = _process_doubles(chars)
    chars = _process_tones(chars, telex_mode=telex_mode, has_doubles=has_doubles)
    return "".join(chars)


def convert_telems(text: str, *, telex_mode: bool = False) -> str:
    """Convert telex ASCII to Vietnamese.

    Args:
        text: Raw input text.
        telex_mode: When True, tone keys at word-end are also converted.
            When False (default), only tone keys *between* two vowels are
            converted, so English words like ``world`` and ``project``
            are preserved.
    """
    parts = re.split(r"(\s+)", text)
    return "".join(_process_token(p, telex_mode=telex_mode) for p in parts)


__all__ = ["convert_telems"]
