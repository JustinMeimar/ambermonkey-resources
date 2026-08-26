"""Cumulative held-out coverage for prefixes of the tp6-Train corpus."""

from collections import Counter

STANDALONE_IC_DYNAMIC_ORDER = (
    "ascending standalone IC dynamic coverage of pooled tp6-Test; "
    "site-name tie-breaker"
)


def pooled_set(sets_by_site, sites):
    return set().union(*(sets_by_site[site] for site in sites))


def pooled_counter(counters_by_site, sites):
    total = Counter()
    for site in sites:
        total.update(counters_by_site[site])
    return total


def static_intersection(source, target):
    union = source | target
    return len(source & target) / len(union) if union else 0.0


def dynamic_coverage(source, target_frequencies):
    total = sum(target_frequencies.values())
    if not total:
        return 0.0
    covered = sum(
        count for identity, count in target_frequencies.items() if identity in source
    )
    return covered / total


def rank_by_standalone_ic_dynamic(
    train_sites, test_sites, ic_sets, ic_frequencies
):
    """Put the least-generalizing individual IC corpora first.

    The key is measured once per workload against the complete pooled test
    oracle. It does not depend on which workloads precede it in the curve.
    Site name provides a deterministic tie-breaker.
    """
    test_ic_frequencies = pooled_counter(ic_frequencies, test_sites)
    return tuple(
        sorted(
            train_sites,
            key=lambda site: (
                dynamic_coverage(ic_sets[site], test_ic_frequencies),
                site,
            ),
        )
    )


def coverage_curve(
    train_sites,
    test_sites,
    ic_sets,
    ic_frequencies,
    baseline_sets,
    baseline_frequencies,
    *,
    order_policy="caller-specified",
):
    """Measure each cumulative training prefix against the pooled test oracle."""
    test_ic_set = pooled_set(ic_sets, test_sites)
    test_ic_frequencies = pooled_counter(ic_frequencies, test_sites)
    test_baseline_set = pooled_set(baseline_sets, test_sites)
    test_baseline_frequencies = pooled_counter(baseline_frequencies, test_sites)

    missing_ic = set(test_ic_frequencies) - test_ic_set
    missing_baseline = set(test_baseline_frequencies) - test_baseline_set
    if missing_ic or missing_baseline:
        raise ValueError(
            "test entries without matching requests: "
            f"IC={len(missing_ic)}, Baseline={len(missing_baseline)}"
        )

    cumulative_ic = set()
    cumulative_baseline = set()
    points = []
    for corpus_size, site in enumerate(train_sites, start=1):
        cumulative_ic.update(ic_sets[site])
        cumulative_baseline.update(baseline_sets[site])
        points.append(
            {
                "corpus_size": corpus_size,
                "added_site": site,
                "added_site_ic_dynamic": dynamic_coverage(
                    ic_sets[site], test_ic_frequencies
                ),
                "ic_static": static_intersection(cumulative_ic, test_ic_set),
                "ic_dynamic": dynamic_coverage(
                    cumulative_ic, test_ic_frequencies
                ),
                "baseline_static": static_intersection(
                    cumulative_baseline, test_baseline_set
                ),
                "baseline_dynamic": dynamic_coverage(
                    cumulative_baseline, test_baseline_frequencies
                ),
            }
        )

    return {
        "train_sites": list(train_sites),
        "test_sites": list(test_sites),
        "order_policy": order_policy,
        "test_oracle": {
            "ic_distinct": len(test_ic_set),
            "ic_entries": sum(test_ic_frequencies.values()),
            "baseline_distinct": len(test_baseline_set),
            "baseline_entries": sum(test_baseline_frequencies.values()),
        },
        "points": points,
    }
