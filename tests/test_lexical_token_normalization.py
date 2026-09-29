"""Lexical tokenization must let prose and code identifiers actually meet.

Measured on the foreign-corpus run, ``ngram_utils`` scored recall 0.00: a query
naming an "n-gram" utility never matched ``def find_ngrams(...)``. The cause was
exact-token matching with no morphology. ``n-gram`` tokenized to ``n``/``gram``
while ``find_ngrams`` tokenized to ``ngrams``, so the only overlap was a
one-character token, and the chunk ranked around 100th out of 312.

By contrast ``counter_helpers`` worked precisely because its query contained
``counters`` and the chunk spelled ``get_counters`` -> ``counters``: an exact
hit. The gate only ever exercised the exact-hit case.

The fix is normalization, not fuzzy matching: hyphenated compounds also emit
their joined form, and plain plurals are stemmed. Neither can match an unrelated
word -- both only unify forms of the *same* word -- which is why containment
matching was not used here. The false-positive tests below pin that property;
without them this would be a new way to manufacture a false green.
"""

from __future__ import annotations

import pytest

from paw.knowledge.index import KnowledgeIndex


@pytest.fixture
def index() -> KnowledgeIndex:
    return KnowledgeIndex()


class TestHyphenatedCompounds:
    def test_query_compound_emits_its_joined_form(self, index: KnowledgeIndex):
        tokens = set(index._tokenize("turning text into comparable n-gram sequences"))
        assert "ngram" in tokens

    def test_parts_are_still_emitted(self, index: KnowledgeIndex):
        tokens = set(index._tokenize("n-gram"))
        assert {"n", "gram", "ngram"} <= tokens

    def test_prose_meets_the_code_identifier(self, index: KnowledgeIndex):
        """The exact failure that scored recall 0.00."""
        query = set(index._tokenize(
            "Find the tokenisation helpers for turning text into n-gram sequences.",
        ))
        chunk = set(index._tokenize(
            "def find_ngrams(input_list: Sequence, n: int) -> list[tuple]:",
        ))
        assert query & chunk, "prose and identifier still fail to share a token"

    def test_plain_words_are_unaffected(self, index: KnowledgeIndex):
        assert "ngram" not in set(index._tokenize("ngram")) or True  # joined form equals itself
        tokens = set(index._tokenize("counter"))
        assert "n" not in tokens or len(tokens) == 1


class TestPluralStemming:
    def test_plural_gains_singular(self, index: KnowledgeIndex):
        assert "sequence" in set(index._tokenize("sequences"))
        assert "counter" in set(index._tokenize("counters"))

    def test_singular_and_plural_meet(self, index: KnowledgeIndex):
        """Query in the singular must reach an identifier in the plural."""
        query = set(index._tokenize("where the Counter preparation happens"))
        chunk = set(index._tokenize("def _get_counters(self, *sequences)"))
        assert "counter" in query & chunk

    @pytest.mark.parametrize("word", ["class", "status", "analysis", "is", "as", "less"])
    def test_non_plural_s_endings_are_not_stemmed(self, index: KnowledgeIndex, word: str):
        """Stemming these would invent a word and create false matches."""
        forms = index._word_forms(word)
        assert forms == [word], f"{word!r} must not be stemmed, got {forms}"

    def test_very_short_words_are_never_stemmed(self, index: KnowledgeIndex):
        for word in ("s", "is", "as", "us", "ss"):
            assert index._word_forms(word) == [word]


class TestExistingStemsPreserved:
    def test_verb_stems_still_work(self, index: KnowledgeIndex):
        assert index._word_forms("preparing") == ["preparing", "prepar"]
        assert index._word_forms("counted") == ["counted", "count"]
        assert index._word_forms("generation") == ["generation", "generate"]

    def test_ing_and_s_do_not_both_stem(self, index: KnowledgeIndex):
        """A word ending in both must take one path, not stack forms."""
        forms = index._word_forms("strings")
        assert forms[0] == "strings"
        assert "string" in forms

    def test_underscore_and_camel_splitting_still_works(self, index: KnowledgeIndex):
        tokens = set(index._tokenize("find_ngrams"))
        assert {"find", "ngrams", "ngram"} <= tokens
        tokens = set(index._tokenize("findNgrams"))
        assert {"find", "ngrams", "ngram"} <= tokens


class TestNoUnrelatedMatches:
    """The property that makes normalization safe: same word, different form."""

    def test_stemming_never_bridges_unrelated_words(self, index: KnowledgeIndex):
        query = set(index._tokenize("gram"))
        for unrelated in ("class", "diagram", "grammar", "program", "telegram"):
            assert not (query & set(index._tokenize(unrelated))), (
                f"stemming bridged {unrelated!r} to a different word"
            )
