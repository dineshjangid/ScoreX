"""Scale a fitted logistic regression + its binning into a points
scorecard, using the standard PDO (points-to-double-odds) formula:

    factor = PDO / ln(2)
    offset = base_score - factor * ln(base_odds)
    score  = offset + factor * ln(odds_of_good)

Since the model predicts P(bad) as logit^-1(const + sum(coef_i * WOE_i))
with WOE = ln(dist_good/dist_bad), ln(odds_of_good) = -(const + sum(coef_i
* WOE_i)), so each bin's point contribution is -factor * coef_i * WOE_i,
and the constant term contributes a "base points" of offset - factor *
const.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ScalingConfig:
    pdo: float = 20.0
    base_score: float = 600.0
    base_odds: float = 50.0  # good:bad odds at base_score

    def to_dict(self) -> dict[str, Any]:
        return {"pdo": self.pdo, "base_score": self.base_score, "base_odds": self.base_odds}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScalingConfig":
        return cls(pdo=data.get("pdo", 20.0), base_score=data.get("base_score", 600.0), base_odds=data.get("base_odds", 50.0))


@dataclass
class BinPoints:
    label: str
    woe: float
    points: int

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "woe": self.woe, "points": self.points}


@dataclass
class VariablePoints:
    variable: str
    coefficient: float
    bins: list[BinPoints]

    def to_dict(self) -> dict[str, Any]:
        return {"variable": self.variable, "coefficient": self.coefficient, "bins": [b.to_dict() for b in self.bins]}


@dataclass
class Scorecard:
    factor: float
    offset: float
    base_points: int
    variables: list[VariablePoints]
    min_score: int
    max_score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor": self.factor,
            "offset": self.offset,
            "base_points": self.base_points,
            "variables": [v.to_dict() for v in self.variables],
            "min_score": self.min_score,
            "max_score": self.max_score,
        }


def build_scorecard(
    fitted_params: dict[str, float],
    binning_variables: dict[str, dict],
    config: ScalingConfig,
) -> Scorecard:
    factor = config.pdo / np.log(2)
    offset = config.base_score - factor * np.log(config.base_odds)
    const = fitted_params["const"]

    variables_out: list[VariablePoints] = []
    for var, coef in fitted_params.items():
        if var == "const":
            continue
        binning = binning_variables[var]
        bins_out = [
            BinPoints(label=b["label"], woe=b["woe"], points=int(round(-factor * coef * b["woe"])))
            for b in binning["bins"]
        ]
        variables_out.append(VariablePoints(variable=var, coefficient=coef, bins=bins_out))

    base_points = int(round(offset - factor * const))
    min_score = base_points + sum(min(b.points for b in v.bins) for v in variables_out) if variables_out else base_points
    max_score = base_points + sum(max(b.points for b in v.bins) for v in variables_out) if variables_out else base_points

    return Scorecard(
        factor=float(factor),
        offset=float(offset),
        base_points=base_points,
        variables=variables_out,
        min_score=int(min_score),
        max_score=int(max_score),
    )
