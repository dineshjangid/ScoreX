"""Alternative (non-scorecard) model benchmarking with SHAP explainability.

Fits a tree-ensemble classifier on the raw (non-WOE-transformed) variables and
compares its discrimination against the logistic-regression scorecard. Several
algorithms are supported so an analyst can benchmark the scorecard against more
than one challenger model.

The feature-encoding and SHAP helpers here (`categorical_categories`,
`apply_feature_encoding`, `shap_matrix`) are also reused by `fit_model`/
`predict_bad_proba` (for scoring new data once one of these algorithms has
been picked as the project's final model) and by `reason_codes` (for
per-row SHAP-based adverse action reasons).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

Algorithm = Literal["xgboost", "random_forest", "lightgbm", "catboost"]
FeatureMode = Literal["category", "raw_str", "ordinal"]

ALL_ALGORITHMS: list[Algorithm] = ["xgboost", "random_forest", "lightgbm", "catboost"]

ALGORITHM_LABELS: dict[Algorithm, str] = {
    "xgboost": "XGBoost",
    "random_forest": "Random Forest",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
}

# Which feature encoding each algorithm needs for its non-numeric columns —
# see apply_feature_encoding() for what each mode does.
FEATURE_MODE: dict[Algorithm, FeatureMode] = {
    "xgboost": "category",
    "lightgbm": "category",
    "catboost": "raw_str",
    "random_forest": "ordinal",
}


@dataclass
class FeatureImportance:
    variable: str
    mean_abs_shap: float

    def to_dict(self) -> dict[str, Any]:
        return {"variable": self.variable, "mean_abs_shap": self.mean_abs_shap}


@dataclass
class MLBenchmarkResult:
    algorithm: Algorithm
    variables: list[str]
    train_auc: float
    test_auc: float
    train_gini: float
    test_gini: float
    feature_importance: list[FeatureImportance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "variables": self.variables,
            "train_auc": self.train_auc,
            "test_auc": self.test_auc,
            "train_gini": self.train_gini,
            "test_gini": self.test_gini,
            "feature_importance": [f.to_dict() for f in self.feature_importance],
        }


def categorical_categories(train_df: pd.DataFrame, variables: list[str]) -> dict[str, list[str]]:
    """For each non-numeric variable, the sorted list of string categories
    seen in the training data. Persisting this alongside a fitted model lets
    new data be encoded identically at inference time (see
    apply_feature_encoding), with any category unseen at training time
    falling into pandas' "unknown category" bucket (NaN / code -1) rather
    than raising.
    """
    categories: dict[str, list[str]] = {}
    for col in variables:
        if pd.api.types.is_numeric_dtype(train_df[col]) and not pd.api.types.is_bool_dtype(train_df[col]):
            continue
        categories[col] = sorted(train_df[col].astype(str).unique())
    return categories


def apply_feature_encoding(
    df: pd.DataFrame,
    variables: list[str],
    categories: dict[str, list[str]],
    mode: FeatureMode,
) -> pd.DataFrame:
    """Encodes `df`'s columns the way `mode` needs them, using a fixed
    `categories` mapping (from categorical_categories on the training data)
    so any data — train, test, or brand-new records at scoring time — is
    encoded identically.

    - "category": pandas Categorical dtype (native support in XGBoost/LightGBM).
    - "raw_str": plain string columns (CatBoost prefers this over pandas categoricals).
    - "ordinal": integer category codes (sklearn's RandomForestClassifier needs numeric input).
    """
    X = df[variables].copy()
    for col in variables:
        if col not in categories:
            continue
        col_str = X[col].astype(str)
        if mode == "raw_str":
            X[col] = col_str
        else:
            # Map anything unseen at training time to NaN *before*
            # categorizing (rather than passing it straight to
            # pd.Categorical/astype with a restricted `categories`), since
            # constructing a categorical from out-of-vocabulary values is
            # deprecated in pandas and will raise in a future version.
            known = col_str.where(col_str.isin(categories[col]))
            cat = pd.Categorical(known, categories=categories[col])
            X[col] = cat if mode == "category" else cat.codes
    return X


def _build_model(
    algorithm: Algorithm,
    cat_feature_idx: list[int],
    n_estimators: int,
    max_depth: int,
    random_state: int,
):
    if algorithm == "random_forest":
        return RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth or None,
            random_state=random_state,
        )
    if algorithm == "lightgbm":
        import lightgbm as lgb

        return lgb.LGBMClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            verbosity=-1,
        )
    if algorithm == "catboost":
        import catboost as cb

        return cb.CatBoostClassifier(
            iterations=n_estimators,
            depth=max_depth,
            random_state=random_state,
            cat_features=cat_feature_idx or None,
            verbose=False,
            allow_writing_files=False,
        )
    if algorithm == "xgboost":
        import xgboost as xgb

        return xgb.XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            enable_categorical=True,
            eval_metric="logloss",
        )
    raise ValueError(f"Unknown algorithm: {algorithm}")


def fit_model(
    train_df: pd.DataFrame,
    train_bad: pd.Series,
    variables: list[str],
    algorithm: Algorithm,
    n_estimators: int = 100,
    max_depth: int = 3,
    random_state: int = 42,
):
    """Fits and returns just the raw model object (plus the categorical
    encoding it needs), for callers that want to keep/persist the fitted
    model itself rather than only its benchmark metrics — e.g. picking one
    of these algorithms as the project's final model."""
    categories = categorical_categories(train_df, variables)
    mode = FEATURE_MODE[algorithm]
    X_train = apply_feature_encoding(train_df, variables, categories, mode)
    cat_feature_idx = [i for i, col in enumerate(variables) if col in categories]
    model = _build_model(algorithm, cat_feature_idx, n_estimators, max_depth, random_state)
    model.fit(X_train, train_bad)
    return model, categories


def predict_bad_proba(
    model,
    df: pd.DataFrame,
    variables: list[str],
    categories: dict[str, list[str]],
    algorithm: Algorithm,
) -> pd.Series:
    """P(bad) for each row of `df`, from a fitted model produced by fit_model
    (or fit_ml_benchmark), encoding `df` the same way the model was trained on."""
    if len(df) == 0:
        # Some libraries (LightGBM) reject an empty 2D input outright rather
        # than returning an empty prediction — e.g. an unused OOT sample.
        return pd.Series([], index=df.index, dtype=float)
    X = apply_feature_encoding(df, variables, categories, FEATURE_MODE[algorithm])
    return pd.Series(model.predict_proba(X)[:, 1], index=df.index)


def shap_matrix(model, X: pd.DataFrame) -> np.ndarray:
    """Per-row, per-column SHAP contribution to the "bad" class, as a plain
    2D array. SHAP's raw return shape varies by model/version: some binary
    classifiers (e.g. sklearn's RandomForestClassifier) return a list of
    per-class arrays, others return a single 2D array, and newer SHAP
    versions return a 3D array of shape (n_samples, n_features, n_classes).
    This normalizes all of them to (n_samples, n_features)."""
    explainer = shap.TreeExplainer(model)
    raw = explainer.shap_values(X)
    if isinstance(raw, list):
        raw = raw[-1]
    arr = np.asarray(raw)
    if arr.ndim == 3:
        arr = arr[:, :, -1]
    return arr


def _shap_feature_importance(model, X_train: pd.DataFrame, variables: list[str]) -> list[FeatureImportance]:
    mean_abs_shap = np.abs(shap_matrix(model, X_train)).mean(axis=0)
    importances = [
        FeatureImportance(variable=var, mean_abs_shap=round(float(v), 4)) for var, v in zip(variables, mean_abs_shap)
    ]
    return sorted(importances, key=lambda f: f.mean_abs_shap, reverse=True)


def fit_ml_benchmark(
    train_df: pd.DataFrame,
    train_bad: pd.Series,
    test_df: pd.DataFrame,
    test_bad: pd.Series,
    variables: list[str],
    algorithm: Algorithm = "xgboost",
    n_estimators: int = 100,
    max_depth: int = 3,
    random_state: int = 42,
) -> MLBenchmarkResult:
    model, categories = fit_model(train_df, train_bad, variables, algorithm, n_estimators, max_depth, random_state)
    mode = FEATURE_MODE[algorithm]
    X_train = apply_feature_encoding(train_df, variables, categories, mode)

    train_pred = model.predict_proba(X_train)[:, 1]
    test_pred = predict_bad_proba(model, test_df, variables, categories, algorithm)

    train_auc = roc_auc_score(train_bad, train_pred)
    train_gini = 2 * train_auc - 1

    if test_bad.nunique() < 2:
        # Degenerate test sample (no bads, or no goods): AUC is undefined,
        # so report the no-discrimination baseline rather than erroring.
        test_auc = 0.5
        test_gini = 0.0
    else:
        test_auc = roc_auc_score(test_bad, test_pred)
        test_gini = 2 * test_auc - 1

    feature_importance = _shap_feature_importance(model, X_train, variables)

    return MLBenchmarkResult(
        algorithm=algorithm,
        variables=variables,
        train_auc=round(float(train_auc), 4),
        test_auc=round(float(test_auc), 4),
        train_gini=round(float(train_gini), 4),
        test_gini=round(float(test_gini), 4),
        feature_importance=feature_importance,
    )


def fit_all_benchmarks(
    train_df: pd.DataFrame,
    train_bad: pd.Series,
    test_df: pd.DataFrame,
    test_bad: pd.Series,
    variables: list[str],
    n_estimators: int = 100,
    max_depth: int = 3,
    random_state: int = 42,
) -> list[MLBenchmarkResult]:
    return [
        fit_ml_benchmark(
            train_df,
            train_bad,
            test_df,
            test_bad,
            variables,
            algorithm=algo,
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
        )
        for algo in ALL_ALGORITHMS
    ]
