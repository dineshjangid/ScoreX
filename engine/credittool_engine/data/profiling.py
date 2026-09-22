"""Per-column and dataset-level profiling for an uploaded raw dataset."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _column_kind(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "categorical"


def profile_column(series: pd.Series) -> dict[str, Any]:
    n = len(series)
    missing = int(series.isna().sum())
    kind = _column_kind(series)
    profile: dict[str, Any] = {
        "name": str(series.name),
        "kind": kind,
        "count": n,
        "missing_count": missing,
        "missing_pct": round(missing / n * 100, 2) if n else 0.0,
        "n_unique": int(series.nunique(dropna=True)),
    }

    non_null = series.dropna()
    if kind == "numeric" and not non_null.empty:
        described = non_null.astype(float).describe(percentiles=[0.25, 0.5, 0.75])
        std = float(described["std"])
        profile["stats"] = {
            "mean": round(float(described["mean"]), 4),
            "std": 0.0 if np.isnan(std) else round(std, 4),
            "min": round(float(described["min"]), 4),
            "p25": round(float(described["25%"]), 4),
            "median": round(float(described["50%"]), 4),
            "p75": round(float(described["75%"]), 4),
            "max": round(float(described["max"]), 4),
        }
    elif kind in {"categorical", "boolean"} and not non_null.empty:
        top = non_null.astype(str).value_counts().head(10)
        profile["top_values"] = [
            {"value": val, "count": int(cnt), "pct": round(cnt / n * 100, 2)}
            for val, cnt in top.items()
        ]
    return profile


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "columns": [profile_column(df[col]) for col in df.columns],
    }
