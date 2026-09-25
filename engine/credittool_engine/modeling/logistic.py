"""Logistic regression on WOE-transformed variables — the traditional
scorecard model, predicting P(bad). Fit with statsmodels for full
diagnostics (coefficient, std error, p-value) rather than sklearn.

An optional L1 or L2 penalty shrinks coefficients to curb overfitting.
Penalised fits have no standard errors or p-values (statsmodels doesn't
produce them for regularised estimates), so those fields are None, and an
L1 penalty can zero a variable out entirely — it is then dropped from the
model and listed in `dropped_variables`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm


Penalty = Literal["none", "l1", "l2"]

# |coefficient| below this after an L1 fit counts as zeroed out.
_ZERO_COEF = 1e-6


@dataclass
class CoefficientRow:
    variable: str
    coefficient: float
    std_error: float | None
    p_value: float | None
    z_value: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "coefficient": self.coefficient,
            "std_error": self.std_error,
            "p_value": self.p_value,
            "z_value": self.z_value,
        }


@dataclass
class LogisticModel:
    variables: list[str]
    intercept: float
    coefficients: list[CoefficientRow]
    n_obs: int
    log_likelihood: float
    pseudo_r2: float
    aic: float
    fitted_params: dict[str, float]  # {"const": ..., var: coef, ...}, used to score new data
    penalty: Penalty = "none"
    alpha: float = 0.0
    # Requested variables an L1 penalty shrank to exactly zero.
    dropped_variables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "penalty": self.penalty,
            "alpha": self.alpha,
            "dropped_variables": self.dropped_variables,
            "variables": self.variables,
            "intercept": self.intercept,
            "coefficients": [c.to_dict() for c in self.coefficients],
            "n_obs": self.n_obs,
            "log_likelihood": self.log_likelihood,
            "pseudo_r2": self.pseudo_r2,
            "aic": self.aic,
            "fitted_params": self.fitted_params,
        }


def fit_logistic_regression(
    woe_frame: pd.DataFrame,
    bad_flag: pd.Series,
    variables: list[str],
    penalty: Penalty = "none",
    alpha: float = 0.0,
) -> LogisticModel:
    """Fit P(bad) on the given WOE columns. `alpha` is the penalty strength
    on the mean log-likelihood scale (statsmodels' elastic-net convention);
    the intercept is never penalised. penalty="none" or alpha=0 is a plain
    maximum-likelihood fit with full diagnostics."""
    if penalty != "none" and alpha > 0:
        return _fit_penalised(woe_frame, bad_flag, variables, penalty, alpha)

    design = sm.add_constant(woe_frame[variables], has_constant="add")
    fit_result = sm.Logit(bad_flag.astype(float), design).fit(disp=0)

    coefficients = [
        CoefficientRow(
            variable=var,
            coefficient=round(float(fit_result.params[var]), 6),
            std_error=round(float(fit_result.bse[var]), 6),
            p_value=round(float(fit_result.pvalues[var]), 6),
            z_value=round(float(fit_result.tvalues[var]), 4),
        )
        for var in variables
    ]

    fitted_params = {"const": float(fit_result.params["const"])}
    fitted_params.update({var: float(fit_result.params[var]) for var in variables})

    return LogisticModel(
        variables=variables,
        intercept=round(float(fit_result.params["const"]), 6),
        coefficients=coefficients,
        n_obs=int(fit_result.nobs),
        log_likelihood=round(float(fit_result.llf), 4),
        pseudo_r2=round(float(fit_result.prsquared), 4),
        aic=round(float(fit_result.aic), 4),
        fitted_params=fitted_params,
    )


def _bernoulli_log_likelihood(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _fit_penalised(
    woe_frame: pd.DataFrame, bad_flag: pd.Series, variables: list[str], penalty: Penalty, alpha: float
) -> LogisticModel:
    y = bad_flag.astype(float).to_numpy()
    design = sm.add_constant(woe_frame[variables], has_constant="add")
    # Per-parameter penalty weights: 0 for the intercept, alpha for the rest.
    weights = np.array([0.0 if col == "const" else alpha for col in design.columns])
    fit_result = sm.GLM(y, design, family=sm.families.Binomial()).fit_regularized(
        method="elastic_net", alpha=weights, L1_wt=1.0 if penalty == "l1" else 0.0
    )
    params = pd.Series(np.asarray(fit_result.params, dtype=float), index=design.columns)

    kept = [v for v in variables if penalty != "l1" or abs(params[v]) > _ZERO_COEF]
    dropped = [v for v in variables if v not in kept]

    fitted_params = {"const": float(params["const"])}
    fitted_params.update({var: float(params[var]) for var in kept})
    p_bad = predict_probability(woe_frame[kept], fitted_params).to_numpy()

    llf = _bernoulli_log_likelihood(y, p_bad)
    llnull = _bernoulli_log_likelihood(y, np.full_like(y, y.mean()))
    n_params = len(kept) + 1

    return LogisticModel(
        variables=kept,
        intercept=round(float(params["const"]), 6),
        coefficients=[
            CoefficientRow(variable=var, coefficient=round(float(params[var]), 6), std_error=None, p_value=None, z_value=None)
            for var in kept
        ],
        n_obs=int(len(y)),
        log_likelihood=round(llf, 4),
        pseudo_r2=round(1 - llf / llnull, 4) if llnull != 0 else 0.0,
        aic=round(2 * n_params - 2 * llf, 4),
        fitted_params=fitted_params,
        penalty=penalty,
        alpha=alpha,
        dropped_variables=dropped,
    )


def predict_probability(woe_frame: pd.DataFrame, fitted_params: dict[str, float]) -> pd.Series:
    """P(bad) for each row, from a fitted model's params dict."""
    variables = [v for v in fitted_params if v != "const"]
    linear = pd.Series(fitted_params["const"], index=woe_frame.index, dtype=float)
    for var in variables:
        linear = linear + fitted_params[var] * woe_frame[var]
    return 1 / (1 + np.exp(-linear))
