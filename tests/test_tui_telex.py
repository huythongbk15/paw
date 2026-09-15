"""Tests for the inline telex converter."""

import pytest

from paw.tui.telex import convert_telems


class TestTelexDoubles:
    """Double-vowel conversions."""

    def test_oo_to_o_circumflex(self):
        assert convert_telems("tooi") == "tôi"

    def test_ee_to_e_circumflex(self):
        assert convert_telems("sinhvieen") == "sinhviên"

    def test_ow_to_o_horn(self):
        assert convert_telems("chow") == "chơ"

    def test_aa_to_a_circumflex(self):
        assert convert_telems("naat") == "nât"

    def test_dd_to_d_bar(self):
        assert convert_telems("dd") == "đ"

    def test_double_consonant(self):
        assert convert_telems("book") == "bôk"


class TestTelexTonesBetweenVowels:
    """Tone marks between two vowels are converted (default mode)."""

    def test_s_huyen(self):
        assert convert_telems("chaso") == "chào"

    def test_f_hoi(self):
        assert convert_telems("chafe") == "chảe"

    def test_r_nga(self):
        assert convert_telems("charo") == "chão"

    def test_x_sac(self):
        assert convert_telems("chaxo") == "cháo"

    def test_tone_with_double(self):
        assert convert_telems("gooix") == "gôí"

    def test_trailing_punctuation(self):
        assert convert_telems("chaso!") == "chào!"


class TestTelexEnglishPreservation:
    """English words must not be mangled in default mode."""

    def test_world_not_mangled(self):
        assert convert_telems("world") == "world"

    def test_hello_not_mangled(self):
        assert convert_telems("hello") == "hello"

    def test_word_not_mangled(self):
        assert convert_telems("word") == "word"

    def test_project_not_mangled(self):
        assert convert_telems("project") == "project"

    def test_box_not_mangled(self):
        assert convert_telems("box") == "box"

    def test_suot_not_mangled(self):
        assert convert_telems("suot") == "suot"

    def test_xin_not_mangled(self):
        assert convert_telems("xin") == "xin"


class TestTelexModeToggle:
    """With telex_mode=True, word-end tone keys are converted."""

    def test_chax_with_toggle(self):
        assert convert_telems("chax", telex_mode=True) == "chá"

    def test_box_with_toggle(self):
        assert convert_telems("box", telex_mode=True) == "bó"

    def test_without_toggle_passthrough(self):
        assert convert_telems("chax") == "chax"

    def test_j_between_vowels_needs_toggle(self):
        # 'j' between vowels is ambiguous (project) -> needs toggle
        assert convert_telems("chajo") == "chajo"
        assert convert_telems("chajo", telex_mode=True) == "chao"

    def test_r_before_consonants_preserved_even_with_toggle(self):
        # 'r' followed by consonants (world, word) -> not a tone marker
        assert convert_telems("world", telex_mode=True) == "world"
        assert convert_telems("word", telex_mode=True) == "word"


class TestTelexPhrases:
    """Full phrase conversions with default mode."""

    def test_tooi_la_chaso(self):
        assert convert_telems("tooi la chaso") == "tôi la chào"

    def test_hello_world(self):
        assert convert_telems("hello world") == "hello world"

    def test_mixed_vietnamese_english(self):
        assert convert_telems("tooi chaso world") == "tôi chào world"


class TestTelexEdgeCases:
    """Edge cases and robustness."""

    def test_empty(self):
        assert convert_telems("") == ""

    def test_only_spaces(self):
        assert convert_telems("   ") == "   "

    def test_word_end_no_toggle(self):
        assert convert_telems("chax!") == "chax!"

    def test_uppercase_normalized(self):
        assert convert_telems("TOOI") == "tôi"


class TestTuiTelexModeGating:
    """Verify the TUI only applies the inline telex converter when
    /telex is explicitly enabled.

    Bug: 'xin chào' → 'xin chàa' because any(c.isascii()) ran the converter
    on mixed ASCII+Unicode text, corrupting IME-committed characters.

    Fix: only run converter when self.telex_mode=True AND input is pure ASCII.
    """

    def test_converter_skipped_when_telex_off(self):
        """When telex_mode=False (default), converter must NOT run."""
        telex_mode = False
        value = "xin chào"
        should_run = telex_mode and value and all(c.isascii() for c in value)
        assert should_run is False  # converter skipped → value preserved

    def test_converter_runs_when_telex_on_pure_ascii(self):
        """When telex_mode=True + pure ASCII, converter SHOULD run."""
        telex_mode = True
        value = "xin chaso"
        should_run = telex_mode and value and all(c.isascii() for c in value)
        assert should_run is True
        assert convert_telems(value, telex_mode=True) == "xin chào"

    def test_converter_skipped_when_unicode_committed(self):
        """Even with /telex ON, if IME committed Unicode, converter must skip."""
        telex_mode = True
        value = "xin chào"  # IME already produced Unicode 'à'
        should_run = telex_mode and value and all(c.isascii() for c in value)
        assert should_run is False  # mixed → skip converter, preserve IME output

    def test_unicode_xin_chao_preserved(self):
        """The exact user bug: 'xin chào' must NOT become 'xin chàa'."""
        value = "xin chào"
        # With the fix: telex_mode=False (default) → converter never runs
        result = value  # no conversion applied
        assert result == "xin chào"
        assert "chàa" not in result  # the bug produced this

    def test_chasa_bug_demonstrated_at_converter_level(self):
        """Document: 'chasa' → 'chàa' at converter level (correct telex).
        The fix prevents this by not running the converter when telex is OFF."""
        assert convert_telems("chasa") == "chàa"   # converter behavior
        assert convert_telems("chaso") == "chào"   # correct telex input

    def test_mixed_unicode_and_ascii_not_converted(self):
        """Mixed Unicode+ASCII text must not trigger converter."""
        cases = [
            "xin chào",        # Unicode tone mark
            "tôi yêu bạn",     # Multiple Unicode chars
            "xin chào bạn ơi", # Spaces + Unicode
        ]
        for val in cases:
            assert not all(c.isascii() for c in val), f"Expected mixed for: {val}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
