"""Shared literal matching for legacy, V2 and combined retrieval.

Identifiers retain underscores and hyphens. Chinese phrases of at least two
characters can match inside a longer sentence. This is lexical matching; it
does not infer synonyms or decide whether a rule applies to the current task.
"""
from __future__ import annotations

import re
from math import ceil


_TERM = re.compile(r"[^\W\u3400-\u9fff]+(?:-[^\W\u3400-\u9fff]+)*|[\u3400-\u9fff]{2,}")
_CHINESE = re.compile(r"[\u3400-\u9fff]+")
_LITERAL = re.compile(r'`([^`]+)`|"([^"]+)"')
_STOPWORDS = frozenset("""
    a an the and or of to in for on with at by from
    is are was were be been being how what which where when who why
    can could would should do does did i we you it they he she
    my your our their this that these those me us please help
""".split())


def text_terms(text: str) -> set[str]:
    """Keep Unicode words and literal identifiers, without dropping stopwords."""
    return {match.group().casefold() for match in _TERM.finditer(text)}


def query_terms(query: str) -> list[str]:
    """Drop conversational filler, preserving quoted terms and acronyms.

    Uppercase identifiers such as CAN and quoted searches such as `do` remain
    searchable even when their lowercase spelling is an English stopword.
    No project, product or technical vocabulary is treated as filler.
    """
    literal_terms = set()
    for match in _LITERAL.finditer(query):
        literal_terms.update(text_terms(next(group for group in match.groups() if group is not None)))
    terms = []
    for match in _TERM.finditer(query):
        raw = match.group()
        term = raw.casefold()
        if term not in _STOPWORDS or term in literal_terms or (len(raw) > 1 and raw.isupper()):
            terms.append(term)
    return list(dict.fromkeys(terms))


def term_coverage(terms: list[str], text: str) -> int:
    """Count distinct query terms with the same boundaries in every lane."""
    haystack = text.casefold()
    words = text_terms(haystack)
    return sum(term in haystack if _CHINESE.fullmatch(term) else term in words for term in terms)


def required_coverage(terms: list[str]) -> int:
    """Require corroborating terms for detailed queries, rather than one verb.

    Short keyword searches retain partial matching. Three or more distinct
    terms require at least half of them (and at least two). Semantic similarity
    may rank eligible records; a merely positive cosine is not relevance proof.
    """
    return max(2, ceil(len(terms) / 2)) if len(terms) >= 3 else 1
