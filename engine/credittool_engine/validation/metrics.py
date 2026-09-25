"""Scorecard validation: discrimination (KS, AUC/Gini, ROC), calibration
(a decile table), and stability (PSI on score, CSI on each characteristic).

Convention: `score` is "higher = safer" (as produced by scoring.compute_
scores), matching how the rest of this engine treats WOE and points.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

_EPS = 1e-4


def compute_ks(bad_flag: pd.Series, score: pd.Series) -> float:
    """KS statistic (%) between the cumulative good and bad distributions
    of score."""
    order = score.sort_values().index
    bad_sorted = bad_flag.loc[order]
    total_good = int((bad_sorted == 0).sum())
    total_bad = int((bad_sorted == 1).sum())
    if total_good == 0 or total_bad == 0:
        return 0.0
    cum_good = (bad_sorted == 0).cumsum() / total_good
    cum_bad = (bad_sorted == 1).cumsum() / total_bad
    return round(float((cum_good - cum_bad).abs().max()) * 100, 2)


def compute_auc_gini(bad_flag: pd.Series, score: pd.Series) -> tuple[float, float]:
    """AUC/Gini for predicting "bad" — since higher score means safer,
    -score is used as the risk-ranking signal for the positive (bad) class."""
    if bad_flag.nunique() < 2:
        return 0.5, 0.0
    auc = roc_auc_score(bad_flag, -score)
    gini = 2 * auc - 1
    return round(float(auc), 4), round(float(gini), 4)


def discrimination_metrics(bad_flag: pd.Series, p_bad: pd.Series) -> dict[str, Any] | None:
    """KS/AUC/Gini of a P(bad) prediction on one sample, for comparing
    train/test/OOT while tuning a model (before it's scaled to points —
    all three are rank-based, so they equal the scaled score's values).
    None for an empty sample."""
    if len(bad_flag) == 0:
        return None
    safer = -pd.Series(np.asarray(p_bad, dtype=float), index=bad_flag.index)
    auc, gini = compute_auc_gini(bad_flag, safer)
    return {"n_total": int(len(bad_flag)), "ks": compute_ks(bad_flag, safer), "auc": auc, "gini": gini}


def roc_curve_points(bad_flag: pd.Series, score: pd.Series, max_points: int = 50) -> list[dict[str, float]]:
    if bad_flag.nunique() < 2:
        return []
    fpr, tpr, _ = roc_curve(bad_flag, -score)
    idx = np.linspace(0, len(fpr) - 1, min(max_points, len(fpr))).astype(int)
    return [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in idx]


def score_bucket_edges(score: pd.Series, n_bins: int = 10) -> list[float]:
    """Equal-population bucket edges from a reference (train) score, with
    open outer ends so any other sample's scores fall into some bucket.
    Pass these to decile_table(edges=...) to bucket test/OOT on the same
    cut points as train, so their rows line up bucket for bucket."""
    try:
        _, edges = pd.qcut(score, q=n_bins, retbins=True, duplicates="drop")
    except (ValueError, IndexError):
        edges = np.array([], dtype=float)
    inner = sorted({float(e) for e in np.asarray(edges, dtype=float)[1:-1]})
    return [-np.inf, *inner, np.inf]


def _bucket_label(lo: float, hi: float) -> str:
    if np.isinf(lo) and np.isinf(hi):
        return "all"
    if np.isinf(lo):
        return f"≤ {hi:g}"
    if np.isinf(hi):
        return f"> {lo:g}"
    return f"{lo:g}–{hi:g}"


def decile_table(
    bad_flag: pd.Series, score: pd.Series, n_bins: int = 10, edges: list[float] | None = None
) -> list[dict[str, Any]]:
    """One row per score decile, ordered riskiest (lowest score) first —
    the standard lift-chart / calibration table.

    With `edges` (from score_bucket_edges on the train score), rows use
    those fixed buckets instead of this sample's own deciles, and every
    bucket is reported even when empty so samples compare row for row."""
    frame = pd.DataFrame({"score": score, "bad": bad_flag})
    total_bad = int((frame["bad"] == 1).sum())

    def row(label: str, sub: pd.DataFrame) -> dict[str, Any]:
        n_total = len(sub)
        n_bad = int((sub["bad"] == 1).sum())
        return {
            "score_range": label,
            "n_total": int(n_total),
            "n_bad": n_bad,
            "bad_rate_pct": round(n_bad / n_total * 100, 2) if n_total else 0.0,
            "pct_of_total_bad": round(n_bad / total_bad * 100, 2) if total_bad else 0.0,
        }

    if edges is not None:
        codes = pd.cut(frame["score"], bins=edges, labels=False, include_lowest=True)
        return [
            row(_bucket_label(edges[i], edges[i + 1]), frame[codes == i]) for i in range(len(edges) - 1)
        ]

    try:
        frame["decile"] = pd.qcut(frame["score"], q=n_bins, duplicates="drop")
    except ValueError:
        frame["decile"] = pd.Categorical([str(frame["score"].iloc[0])] * len(frame))

    return [row(str(interval), sub) for interval, sub in frame.groupby("decile", observed=True, sort=True)]


def score_histogram(
    score: pd.Series, n_bins: int = 20, value_range: tuple[float, float] | None = None
) -> list[dict[str, Any]]:
    """Equal-width histogram of the score (not equal-population like
    decile_table), for a distribution chart. `pct` is the share of this
    sample in each bin, so samples of different sizes can be overlaid.

    Pass the train score's (min, max) as `value_range` to bin test/OOT on
    the same edges as train; scores outside it are clipped into the end bins.
    """
    if len(score) == 0:
        return []
    lo, hi = value_range if value_range is not None else (float(score.min()), float(score.max()))
    n = int(len(score))
    if lo == hi:
        return [{"bin_start": lo, "bin_end": hi, "count": n, "pct": 100.0}]

    counts, edges = np.histogram(score.clip(lo, hi), bins=n_bins, range=(lo, hi))
    return [
        {
            "bin_start": round(float(edges[i]), 2),
            "bin_end": round(float(edges[i + 1]), 2),
            "count": int(counts[i]),
            "pct": round(float(counts[i]) / n * 100, 2),
        }
        for i in range(len(counts))
    ]


def stability_index(reference_labels: pd.Series, comparison_labels: pd.Series) -> dict[str, Any]:
    """Generic PSI/CSI computation between two label distributions."""
    ref_pct = reference_labels.value_counts(normalize=True)
    comp_pct = comparison_labels.value_counts(normalize=True)
    labels = sorted(set(ref_pct.index) | set(comp_pct.index), key=str)

    index_value = 0.0
    buckets = []
    for label in labels:
        r = float(ref_pct.get(label, 0.0))
        c = float(comp_pct.get(label, 0.0))
        contribution = (c - r) * np.log((c + _EPS) / (r + _EPS))
        index_value += contribution
        buckets.append(
            {
                "bucket": str(label),
                "reference_pct": round(r * 100, 2),
                "comparison_pct": round(c * 100, 2),
                "contribution": round(float(contribution), 4),
            }
        )
    return {"index": round(float(index_value), 4), "buckets": buckets}


def population_stability_index(reference_score: pd.Series, comparison_score: pd.Series, n_bins: int = 10) -> dict[str, Any]:
    """PSI on the total score, bucketed by reference-sample quantiles."""
    try:
        _, edges = pd.qcut(reference_score, q=n_bins, retbins=True, duplicates="drop")
    except ValueError:
        edges = np.array([reference_score.min(), reference_score.max()])
    edges = np.unique(edges.astype(float))
    if len(edges) < 2:
        edges = np.array([reference_score.min(), reference_score.max()])
    edges[0], edges[-1] = -np.inf, np.inf

    ref_labels = pd.cut(reference_score, bins=edges, include_lowest=True).astype(str)
    comp_labels = pd.cut(comparison_score, bins=edges, include_lowest=True).astype(str)
    return stability_index(ref_labels, comp_labels)
