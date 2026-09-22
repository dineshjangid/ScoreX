from __future__ import annotations

from dataclasses import dataclass

from .woe import BinStat

MISSING_LABEL = "Missing"


@dataclass
class VariableBinning:
    variable: str
    kind: str
    iv: float
    bins: list[BinStat]
    cutpoints: list[float] | None = None  # numeric only: finite interior edges, ascending
    categories_map: dict[str, str] | None = None  # categorical only: raw value -> bin label

    def to_dict(self) -> dict:
        return {
            "variable": self.variable,
            "kind": self.kind,
            "iv": self.iv,
            "bins": [b.to_dict() for b in self.bins],
            "cutpoints": self.cutpoints,
            "categories_map": self.categories_map,
        }
