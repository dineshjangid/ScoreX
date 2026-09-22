"""A branch rule routes rows from a parent node into one child. Node
membership for any node in the tree is recomputed on demand by
replaying the chain of branch rules from the root — the same
recompute-from-spec approach the binning module uses for cutpoints/
categories_map, rather than persisting row indices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

BranchOperator = Literal["<=", ">", "missing", "in", "not_in"]


@dataclass
class BranchRule:
    variable: str
    kind: Literal["numeric", "categorical"]
    operator: BranchOperator
    threshold: float | None = None
    values: list[str] | None = None

    def describe(self) -> str:
        if self.kind == "numeric":
            if self.operator == "missing":
                return f"{self.variable} is missing"
            return f"{self.variable} {self.operator} {self.threshold}"
        if self.operator == "missing":
            return f"{self.variable} is missing"
        joined = ", ".join(self.values or [])
        verb = "in" if self.operator == "in" else "not in"
        return f"{self.variable} {verb} {{{joined}}}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "kind": self.kind,
            "operator": self.operator,
            "threshold": self.threshold,
            "values": self.values,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BranchRule":
        return cls(
            variable=data["variable"],
            kind=data["kind"],
            operator=data["operator"],
            threshold=data.get("threshold"),
            values=data.get("values"),
        )


def branch_mask(df: pd.DataFrame, rule: BranchRule) -> pd.Series:
    col = df[rule.variable]
    if rule.kind == "numeric":
        numeric = pd.to_numeric(col, errors="coerce")
        if rule.operator == "missing":
            return numeric.isna()
        if rule.operator == "<=":
            return numeric.notna() & (numeric <= rule.threshold)
        if rule.operator == ">":
            return numeric.notna() & (numeric > rule.threshold)
        raise ValueError(f"invalid numeric operator '{rule.operator}'")

    if rule.operator == "missing":
        return col.isna()
    raw = col.astype(str)
    values = set(rule.values or [])
    if rule.operator == "in":
        return col.notna() & raw.isin(values)
    if rule.operator == "not_in":
        return col.notna() & ~raw.isin(values)
    raise ValueError(f"invalid categorical operator '{rule.operator}'")
