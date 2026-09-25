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

from ..validation.metrics import discrimination_metrics

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
class Hyperparams:
    """Tuning knobs shared across the tree ensembles. None means "library
    default". Not every algorithm has every knob — see HYPERPARAM_SUPPORT;
    unsupported ones are ignored."""

    n_estimators: int = 100
    max_depth: int = 3
    learning_rate: float | None = None
    subsample: float | None = None
    min_samples_leaf: int | None = None
    l2_reg: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "subsample": self.subsample,
            "min_samples_leaf": self.min_samples_leaf,
            "l2_reg": self.l2_reg,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Hyperparams":
        data = data or {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__ and v is not None})


# Which optional Hyperparams each algorithm honours (n_estimators and
# max_depth apply to all four).
HYPERPARAM_SUPPORT: dict[Algorithm, set[str]] = {
    "random_forest": {"subsample", "min_samples_leaf"},
    "xgboost": {"learning_rate", "subsample", "l2_reg"},
    "lightgbm": {"learning_rate", "subsample", "min_samples_leaf", "l2_reg"},
    "catboost": {"learning_rate", "subsample", "l2_reg"},
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
    hyperparams: Hyperparams = field(default_factory=Hyperparams)
    # KS/AUC/Gini per sample ("train", "test", and "oot" when provided).
    sample_metrics: dict[str, dict[str, Any] | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hyperparams": self.hyperparams.to_dict(),
            "sample_metrics": self.sample_metrics,
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


def _build_model(algorithm: Algorithm, cat_feature_idx: list[int], params: Hyperparams, random_state: int):
    supported = HYPERPARAM_SUPPORT[algorithm]
    # Only pass knobs that were set and that this algorithm understands,
    # so everything else stays at the library's own default.
    opt = {k: v for k, v in params.to_dict().items() if k in supported and v is not None}

    if algorithm == "random_forest":
        return RandomForestClassifier(
            n_estimators=params.n_estimators,
            max_depth=params.max_depth or None,
            random_state=random_state,
            **({"max_samples": opt["subsample"]} if "subsample" in opt else {}),
            **({"min_samples_leaf": opt["min_samples_leaf"]} if "min_samples_leaf" in opt else {}),
        )
    if algorithm == "lightgbm":
        import lightgbm as lgb

        return lgb.LGBMClassifier(
            n_estimators=params.n_estimators,
            max_depth=params.max_depth,
            random_state=random_state,
            verbosity=-1,
            **({"learning_rate": opt["learning_rate"]} if "learning_rate" in opt else {}),
            # LightGBM only row-samples when subsample_freq > 0.
            **({"subsample": opt["subsample"], "subsample_freq": 1} if "subsample" in opt else {}),
            **({"min_child_samples": opt["min_samples_leaf"]} if "min_samples_leaf" in opt else {}),
            **({"reg_lambda": opt["l2_reg"]} if "l2_reg" in opt else {}),
        )
    if algorithm == "catboost":
        import catboost as cb

        return cb.CatBoostClassifier(
            iterations=params.n_estimators,
            depth=params.max_depth,
            random_state=random_state,
            cat_features=cat_feature_idx or None,
            verbose=False,
            allow_writing_files=False,
            **({"learning_rate": opt["learning_rate"]} if "learning_rate" in opt else {}),
            **({"subsample": opt["subsample"], "bootstrap_type": "Bernoulli"} if "subsample" in opt else {}),
            **({"l2_leaf_reg": opt["l2_reg"]} if "l2_reg" in opt else {}),
        )
    if algorithm == "xgboost":
        import xgboost as xgb

        return xgb.XGBClassifier(
            n_estimators=params.n_estimators,
            max_depth=params.max_depth,
            random_state=random_state,
            enable_categorical=True,
            eval_metric="logloss",
            **({"learning_rate": opt["learning_rate"]} if "learning_rate" in opt else {}),
            **({"subsample": opt["subsample"]} if "subsample" in opt else {}),
            **({"reg_lambda": opt["l2_reg"]} if "l2_reg" in opt else {}),
        )
    raise ValueError(f"Unknown algorithm: {algorithm}")


def fit_model(
    train_df: pd.DataFrame,
    train_bad: pd.Series,
    variables: list[str],
    algorithm: Algorithm,
    hyperparams: Hyperparams | None = None,
    random_state: int = 42,
):
    """Fits and returns just the raw model object (plus the categorical
    encoding it needs), for callers that want to keep/persist the fitted
    model itself rather than only its benchmark metrics — e.g. picking one
    of these algorithms as the project's final model. Given the same
    hyperparams and random_state, it reproduces fit_ml_benchmark's model."""
    params = hyperparams or Hyperparams()
    categories = categorical_categories(train_df, variables)
    mode = FEATURE_MODE[algorithm]
    X_train = apply_feature_encoding(train_df, variables, categories, mode)
    cat_feature_idx = [i for i, col in enumerate(variables) if col in categories]
    model = _build_model(algorithm, cat_feature_idx, params, random_state)
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
    hyperparams: Hyperparams | None = None,
    random_state: int = 42,
    oot_df: pd.DataFrame | None = None,
    oot_bad: pd.Series | None = None,
) -> MLBenchmarkResult:
    params = hyperparams or Hyperparams()
    model, categories = fit_model(train_df, train_bad, variables, algorithm, params, random_state)
    mode = FEATURE_MODE[algorithm]
    X_train = apply_feature_encoding(train_df, variables, categories, mode)

    train_pred = pd.Series(model.predict_proba(X_train)[:, 1], index=train_df.index)
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

    sample_metrics = {
        "train": discrimination_metrics(train_bad, train_pred),
        "test": discrimination_metrics(test_bad, test_pred),
        "oot": None,
    }
    if oot_df is not None and oot_bad is not None and len(oot_df) > 0:
        sample_metrics["oot"] = discrimination_metrics(
            oot_bad, predict_bad_proba(model, oot_df, variables, categories, algorithm)
        )

    feature_importance = _shap_feature_importance(model, X_train, variables)

    return MLBenchmarkResult(
        algorithm=algorithm,
        variables=variables,
        train_auc=round(float(train_auc), 4),
        test_auc=round(float(test_auc), 4),
        train_gini=round(float(train_gini), 4),
        test_gini=round(float(test_gini), 4),
        feature_importance=feature_importance,
        hyperparams=params,
        sample_metrics=sample_metrics,
    )


def fit_all_benchmarks(
    train_df: pd.DataFrame,
    train_bad: pd.Series,
    test_df: pd.DataFrame,
    test_bad: pd.Series,
    variables: list[str],
    hyperparams: Hyperparams | None = None,
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
            hyperparams=hyperparams,
            random_state=random_state,
        )
        for algo in ALL_ALGORITHMS
    ]
