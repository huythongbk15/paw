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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
