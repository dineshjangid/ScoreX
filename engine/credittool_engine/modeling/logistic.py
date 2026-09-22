"""Logistic regression on WOE-transformed variables — the traditional
scorecard model, predicting P(bad). Fit with statsmodels for full
diagnostics (coefficient, std error, p-value) rather than sklearn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm


@dataclass
class CoefficientRow:
    variable: str
    coefficient: float
    std_error: float
    p_value: float
    z_value: float

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "variables": self.variables,
            "intercept": self.intercept,
            "coefficients": [c.to_dict() for c in self.coefficients],
            "n_obs": self.n_obs,
            "log_likelihood": self.log_likelihood,
            "pseudo_r2": self.pseudo_r2,
            "aic": self.aic,
            "fitted_params": self.fitted_params,
        }


def fit_logistic_regression(woe_frame: pd.DataFrame, bad_flag: pd.Series, variables: list[str]) -> LogisticModel:
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


def predict_probability(woe_frame: pd.DataFrame, fitted_params: dict[str, float]) -> pd.Series:
    """P(bad) for each row, from a fitted model's params dict."""
    variables = [v for v in fitted_params if v != "const"]
    linear = pd.Series(fitted_params["const"], index=woe_frame.index, dtype=float)
    for var in variables:
        linear = linear + fitted_params[var] * woe_frame[var]
    return 1 / (1 + np.exp(-linear))
