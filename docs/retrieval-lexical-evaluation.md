# Lexical retrieval checks

The legacy FTS path, scoped V2 path and combined retrieval now use the same
literal query analyser. It removes a small explicit set of English question
words; quoted terms and uppercase acronyms remain searchable. Identifiers keep
underscores and hyphens. Unicode words retain accents. Chinese phrases of at
least two characters match within longer sentences.

An all-filler query returns no experience candidates. Explicit directives
remain visible in their dedicated lane. Scope, lifecycle eligibility, semantic
ranking and automatic promotion policy are unchanged.

Run the synthetic fixture without calling a service or writing live metrics:

```bash
.venv/bin/python scripts/eval_brain_retrieval.py --output /tmp/retrieval-report.json
```

Add `--check` to return a nonzero status if any independently labelled case
fails. Each case reports missing and unexpected IDs. Summary precision divides
relevant returned IDs by the number of returned IDs; it is not Precision@5.
Recall is averaged over cases with a labelled relevant node. Empty expected
sets are reported separately as abstention cases.

The fixture contains 12 synthetic nodes and 16 questions, with 31 lane checks
in total. The V2 lane has no legacy trigger field, so it does not run the
trigger-only case. All stores are temporary, embeddings are disabled, and the
report verifies that no retrieval or outcome events were created.

The initial implementation passes 13/16 legacy and 10/15 V2 cases. The
shared analyser alone reached 15/16 and 14/15. The coverage gate now requires
one matched term for one- or two-term queries and at least half the meaningful
terms (minimum two) for longer queries. This prevents an isolated shared word
such as `inspect` from admitting a candidate. Both paths now pass all labelled
cases: 16/16 legacy and 15/15 V2, with no expected-failure markers.

The gate deliberately favors abstention; it can reject paraphrases without
literal overlap, including candidates with positive semantic similarity.
Semantic relevance and broad held-out recall still need separate evaluation.
The cutoff is a visible, tested engineering default, not a statistically
calibrated relevance threshold.

The before/after numbers are development fixture results. They are not a held
out benchmark, a real usage success rate or a paired Brain-on/off experiment.
Use the pilot design in `brain-effectiveness-evaluation.md` for that work.
