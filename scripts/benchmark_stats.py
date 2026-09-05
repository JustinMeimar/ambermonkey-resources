"""Statistical helpers shared by benchmark figure scripts."""

from __future__ import annotations

import numpy as np


BOOTSTRAP_RESAMPLES = 20_000


def bootstrap_ratio_ci(
    numerator,
    denominator,
    rng: np.random.Generator,
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
):
    """Return a ratio of means and its two-sided 95% bootstrap errors."""
    numerator = np.asarray(numerator, dtype=float)
    denominator = np.asarray(denominator, dtype=float)
    if numerator.size < 2 or denominator.size < 2:
        raise ValueError("95% confidence intervals require at least two runs")
    if np.any(numerator <= 0) or np.any(denominator <= 0):
        raise ValueError("ratio confidence intervals require positive samples")

    point = numerator.mean() / denominator.mean()
    numerator_draws = numerator[
        rng.integers(0, numerator.size, size=(resamples, numerator.size))
    ].mean(axis=1)
    denominator_draws = denominator[
        rng.integers(0, denominator.size, size=(resamples, denominator.size))
    ].mean(axis=1)
    draws = numerator_draws / denominator_draws
    lower, upper = np.quantile(draws, (0.025, 0.975))
    return point, point - lower, upper - point


def bootstrap_geomean_ratio_ci(
    numerators,
    denominators,
    rng: np.random.Generator,
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
):
    """Return a geometric mean of mean ratios and its 95% bootstrap errors.

    Rows are independent runs and columns are benchmark components. Resampling
    rows preserves within-run correlation between components.
    """
    numerators = np.asarray(numerators, dtype=float)
    denominators = np.asarray(denominators, dtype=float)
    if numerators.ndim != 2 or denominators.ndim != 2:
        raise ValueError("aggregate confidence intervals require 2D run matrices")
    if numerators.shape[0] < 2 or denominators.shape[0] < 2:
        raise ValueError("95% confidence intervals require at least two runs")
    if numerators.shape[1] != denominators.shape[1]:
        raise ValueError("ratio matrices must contain the same components")
    if np.any(numerators <= 0) or np.any(denominators <= 0):
        raise ValueError("ratio confidence intervals require positive samples")

    ratios = numerators.mean(axis=0) / denominators.mean(axis=0)
    point = np.exp(np.log(ratios).mean())
    numerator_draws = numerators[
        rng.integers(0, numerators.shape[0], size=(resamples, numerators.shape[0]))
    ].mean(axis=1)
    denominator_draws = denominators[
        rng.integers(0, denominators.shape[0], size=(resamples, denominators.shape[0]))
    ].mean(axis=1)
    draws = np.exp(np.log(numerator_draws / denominator_draws).mean(axis=1))
    lower, upper = np.quantile(draws, (0.025, 0.975))
    return point, point - lower, upper - point
