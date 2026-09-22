"""An XGBoost benchmark model, fit on raw (non-WOE) features, to compare
against the traditional WOE-logistic scorecard — the same comparison a
model risk team does when asked "how much would a more flexible model
gain over the standard scorecard?" SHAP gives per-feature importance so
the comparison stays explainable rather than a black box.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.metrics import roc_auc_score


@dataclass
class FeatureImportance:
    variable: str
    mean_abs_shap: float

    def to_dict(self) -> dict[str, Any]:
        return {"variable": self.variable, "mean_abs_shap": self.mean_abs_shap}


@dataclass
class MLBenchmarkResult:
    variables: list[str]
    train_auc: float
    test_auc: float
    train_gini: float
    test_gini: float
    feature_importance: list[FeatureImportance]

    def to_dict(self) -> dict[str, Any]:
        return {
            "variables": self.variables,
            "train_auc": self.train_auc,
            "test_auc": self.test_auc,
            "train_gini": self.train_gini,
            "test_gini": self.test_gini,
            "feature_importance": [f.to_dict() for f in self.feature_importance],
        }


def _prep_features(train_df: pd.DataFrame, test_df: pd.DataFrame, variables: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    X_train = train_df[variables].copy()
    X_test = test_df[variables].copy()
    for col in variables:
        if not pd.api.types.is_numeric_dtype(X_train[col]):
            X_train[col] = X_train[col].astype(str).astype("category")
            X_test[col] = X_test[col].astype(str).astype(pd.CategoricalDtype(categories=X_train[col].cat.categories))
    return X_train, X_test


def fit_ml_benchmark(
    train_df: pd.DataFrame,
    train_bad: pd.Series,
    test_df: pd.DataFrame,
    test_bad: pd.Series,
    variables: list[str],
    n_estimators: int = 100,
    max_depth: int = 3,
    random_state: int = 42,
) -> MLBenchmarkResult:
    X_train, X_test = _prep_features(train_df, test_df, variables)

    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_state,
        enable_categorical=True,
        eval_metric="logloss",
    )
    model.fit(X_train, train_bad.astype(int))

    train_pred = model.predict_proba(X_train)[:, 1]
    test_pred = model.predict_proba(X_test)[:, 1]

    def _auc_gini(y_true: pd.Series, y_pred: np.ndarray) -> tuple[float, float]:
        if y_true.nunique() < 2:
            return 0.5, 0.0
        auc = float(roc_auc_score(y_true, y_pred))
        return round(auc, 4), round(2 * auc - 1, 4)

    train_auc, train_gini = _auc_gini(train_bad, train_pred)
    test_auc, test_gini = _auc_gini(test_bad, test_pred)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_train)
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    importance = sorted(
        (FeatureImportance(variable=var, mean_abs_shap=round(float(v), 4)) for var, v in zip(variables, mean_abs_shap)),
        key=lambda f: f.mean_abs_shap,
        reverse=True,
    )

    return MLBenchmarkResult(
        variables=variables,
        train_auc=train_auc,
        test_auc=test_auc,
        train_gini=train_gini,
        test_gini=test_gini,
        feature_importance=importance,
    )
