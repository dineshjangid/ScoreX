"""Alternative (non-scorecard) model benchmarking with SHAP explainability.

Fits a tree-ensemble classifier on the raw (non-WOE-transformed) variables and
compares its discrimination against the logistic-regression scorecard. Several
algorithms are supported so an analyst can benchmark the scorecard against more
than one challenger model.
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

ALL_ALGORITHMS: list[Algorithm] = ["xgboost", "random_forest", "lightgbm", "catboost"]

ALGORITHM_LABELS: dict[Algorithm, str] = {
    "xgboost": "XGBoost",
    "random_forest": "Random Forest",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
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


def _prep_features(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    variables: list[str],
    mode: Literal["category", "raw_str", "ordinal"],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aligns non-numeric columns between train/test for the target model family.

    - "category": pandas Categorical dtype (native support in XGBoost/LightGBM).
    - "raw_str": plain string columns (CatBoost prefers this over pandas categoricals).
    - "ordinal": integer category codes (sklearn's RandomForestClassifier needs numeric input).
    Unseen test-set categories are mapped to the "missing" bucket (NaN / code -1) rather
    than raising, since a benchmark run should never fail on an unseen category.
    """
    X_train = train_df[variables].copy()
    X_test = test_df[variables].copy()

    for col in variables:
        if pd.api.types.is_numeric_dtype(X_train[col]) and not pd.api.types.is_bool_dtype(X_train[col]):
            continue

        train_str = X_train[col].astype(str)
        test_str = X_test[col].astype(str)
        cat_dtype = pd.CategoricalDtype(categories=sorted(train_str.unique()))

        if mode == "raw_str":
            X_train[col] = train_str
            X_test[col] = test_str
        elif mode == "category":
            X_train[col] = train_str.astype(cat_dtype)
            X_test[col] = test_str.astype(cat_dtype)
        else:  # ordinal
            X_train[col] = train_str.astype(cat_dtype).cat.codes
            X_test[col] = test_str.astype(cat_dtype).cat.codes

    return X_train, X_test


def _build_model(
    algorithm: Algorithm,
    variables: list[str],
    X_train: pd.DataFrame,
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

        cat_features = [i for i, col in enumerate(variables) if not pd.api.types.is_numeric_dtype(X_train[col])]
        return cb.CatBoostClassifier(
            iterations=n_estimators,
            depth=max_depth,
            random_state=random_state,
            cat_features=cat_features or None,
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


def _shap_feature_importance(model, X_train: pd.DataFrame, variables: list[str]) -> list[FeatureImportance]:
    explainer = shap.TreeExplainer(model)
    raw = explainer.shap_values(X_train)

    # SHAP's return shape varies by model/version: some binary classifiers
    # (e.g. sklearn's RandomForestClassifier) return a list of per-class arrays,
    # others return a single 2D array, and newer SHAP versions return a 3D
    # array of shape (n_samples, n_features, n_classes). Normalize to 2D,
    # taking the contribution to the positive ("bad") class where relevant.
    if isinstance(raw, list):
        raw = raw[-1]
    arr = np.asarray(raw)
    if arr.ndim == 3:
        arr = arr[:, :, -1]

    mean_abs_shap = np.abs(arr).mean(axis=0)
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
    mode: Literal["category", "raw_str", "ordinal"]
    if algorithm == "random_forest":
        mode = "ordinal"
    elif algorithm == "catboost":
        mode = "raw_str"
    else:
        mode = "category"

    X_train, X_test = _prep_features(train_df, test_df, variables, mode)
    model = _build_model(algorithm, variables, X_train, n_estimators, max_depth, random_state)
    model.fit(X_train, train_bad)

    train_pred = model.predict_proba(X_train)[:, 1]
    test_pred = model.predict_proba(X_test)[:, 1]

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
