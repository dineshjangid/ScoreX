"""CART-style binary decision tree for strategy/policy trees: recursive
binary splitting on Gini or entropy impurity reduction, with manual
split/prune/policy-assignment for interactive editing (the Angoss/
RapidMiner-style workflow: build automatically, then adjust by hand).

Numeric splits are a single threshold (<=, >); a third "missing" child
is added only when the node actually has missing values for that
variable. Categorical splits partition categories into two groups,
found via the standard result that for binary classification the
optimal binary split is a prefix of categories sorted by their bad
rate (Breiman et al.) — this makes an exhaustive subset search
unnecessary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from .rules import BranchRule, branch_mask

Criterion = Literal["gini", "entropy"]


def _impurity(bad_rate: float, criterion: Criterion) -> float:
    if bad_rate <= 0.0 or bad_rate >= 1.0:
        return 0.0
    if criterion == "entropy":
        return float(-(bad_rate * np.log2(bad_rate) + (1 - bad_rate) * np.log2(1 - bad_rate)))
    return float(1 - bad_rate**2 - (1 - bad_rate) ** 2)


def _weighted_impurity(bad_flag: pd.Series, masks: list[pd.Series], criterion: Criterion) -> float:
    n_total = sum(int(m.sum()) for m in masks)
    if n_total == 0:
        return 0.0
    total = 0.0
    for mask in masks:
        n = int(mask.sum())
        if n == 0:
            continue
        rate = float(bad_flag[mask].mean())
        total += (n / n_total) * _impurity(rate, criterion)
    return total


@dataclass
class SplitCandidate:
    variable: str
    kind: Literal["numeric", "categorical"]
    gain: float
    threshold: float | None = None
    left_values: list[str] | None = None
    right_values: list[str] | None = None


@dataclass
class TreeNode:
    id: str
    parent_id: str | None
    depth: int
    branch_rule: BranchRule | None  # how you get here from the parent; None for root
    n_total: int
    n_bad: int
    n_good: int
    bad_rate_pct: float
    is_leaf: bool = True
    split_variable: str | None = None
    split_kind: str | None = None
    split_threshold: float | None = None
    split_left_values: list[str] | None = None
    split_right_values: list[str] | None = None
    children: list[str] = field(default_factory=list)
    policy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "branch_rule": self.branch_rule.to_dict() if self.branch_rule else None,
            "branch_description": self.branch_rule.describe() if self.branch_rule else "All records",
            "n_total": self.n_total,
            "n_bad": self.n_bad,
            "n_good": self.n_good,
            "bad_rate_pct": self.bad_rate_pct,
            "is_leaf": self.is_leaf,
            "split_variable": self.split_variable,
            "split_kind": self.split_kind,
            "split_threshold": self.split_threshold,
            "split_left_values": self.split_left_values,
            "split_right_values": self.split_right_values,
            "children": self.children,
            "policy": self.policy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TreeNode":
        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            depth=data["depth"],
            branch_rule=BranchRule.from_dict(data["branch_rule"]) if data.get("branch_rule") else None,
            n_total=data["n_total"],
            n_bad=data["n_bad"],
            n_good=data["n_good"],
            bad_rate_pct=data["bad_rate_pct"],
            is_leaf=data["is_leaf"],
            split_variable=data.get("split_variable"),
            split_kind=data.get("split_kind"),
            split_threshold=data.get("split_threshold"),
            split_left_values=data.get("split_left_values"),
            split_right_values=data.get("split_right_values"),
            children=data.get("children", []),
            policy=data.get("policy"),
        )


@dataclass
class DecisionTree:
    root_id: str
    nodes: dict[str, TreeNode]

    def to_dict(self) -> dict[str, Any]:
        return {"root_id": self.root_id, "nodes": {k: v.to_dict() for k, v in self.nodes.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionTree":
        return cls(root_id=data["root_id"], nodes={k: TreeNode.from_dict(v) for k, v in data["nodes"].items()})


def _make_node(node_id: str, parent_id: str | None, depth: int, branch_rule: BranchRule | None, bad_flag: pd.Series) -> TreeNode:
    n_total = int(len(bad_flag))
    n_bad = int((bad_flag == 1).sum())
    n_good = n_total - n_bad
    return TreeNode(
        id=node_id,
        parent_id=parent_id,
        depth=depth,
        branch_rule=branch_rule,
        n_total=n_total,
        n_bad=n_bad,
        n_good=n_good,
        bad_rate_pct=round(n_bad / n_total * 100, 2) if n_total else 0.0,
    )


def _numeric_candidate_thresholds(values: pd.Series, max_candidates: int = 50) -> list[float]:
    uniques = np.sort(values.dropna().unique())
    if len(uniques) < 2:
        return []
    midpoints = (uniques[:-1] + uniques[1:]) / 2
    if len(midpoints) > max_candidates:
        idx = np.linspace(0, len(midpoints) - 1, max_candidates).astype(int)
        midpoints = midpoints[idx]
    return [float(m) for m in midpoints]


def _best_numeric_split(
    values: pd.Series, bad_flag: pd.Series, criterion: Criterion, min_leaf_size: int, parent_impurity: float
) -> SplitCandidate | None:
    present_mask = values.notna()
    present_values = values[present_mask]
    present_bad = bad_flag[present_mask]
    best: SplitCandidate | None = None

    for threshold in _numeric_candidate_thresholds(present_values):
        left_mask = present_values <= threshold
        right_mask = ~left_mask
        n_left, n_right = int(left_mask.sum()), int(right_mask.sum())
        if n_left < min_leaf_size or n_right < min_leaf_size:
            continue
        weighted = _weighted_impurity(present_bad, [left_mask, right_mask], criterion)
        gain = parent_impurity - weighted
        if best is None or gain > best.gain:
            best = SplitCandidate(variable=str(values.name), kind="numeric", gain=gain, threshold=threshold)
    return best


def _best_categorical_split(
    values: pd.Series, bad_flag: pd.Series, criterion: Criterion, min_leaf_size: int, parent_impurity: float
) -> SplitCandidate | None:
    present_mask = values.notna()
    raw = values[present_mask].astype(str)
    present_bad = bad_flag[present_mask]
    if raw.nunique() < 2:
        return None

    order = pd.DataFrame({"cat": raw, "bad": present_bad}).groupby("cat")["bad"].mean().sort_values().index.tolist()

    best: SplitCandidate | None = None
    for i in range(1, len(order)):
        left_values, right_values = order[:i], order[i:]
        left_mask = raw.isin(left_values)
        right_mask = ~left_mask
        n_left, n_right = int(left_mask.sum()), int(right_mask.sum())
        if n_left < min_leaf_size or n_right < min_leaf_size:
            continue
        weighted = _weighted_impurity(present_bad, [left_mask, right_mask], criterion)
        gain = parent_impurity - weighted
        if best is None or gain > best.gain:
            best = SplitCandidate(
                variable=str(values.name),
                kind="categorical",
                gain=gain,
                left_values=list(left_values),
                right_values=list(right_values),
            )
    return best


def find_best_split(
    df: pd.DataFrame,
    bad_flag: pd.Series,
    candidate_vars: list[str],
    criterion: Criterion,
    min_leaf_size: int,
) -> SplitCandidate | None:
    if bad_flag.nunique() < 2:
        return None
    parent_impurity = _impurity(float(bad_flag.mean()), criterion)

    best: SplitCandidate | None = None
    for var in candidate_vars:
        series = df[var]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            candidate = _best_numeric_split(series, bad_flag, criterion, min_leaf_size, parent_impurity)
        else:
            candidate = _best_categorical_split(series, bad_flag, criterion, min_leaf_size, parent_impurity)
        if candidate is not None and candidate.gain > 1e-12 and (best is None or candidate.gain > best.gain):
            best = candidate
    return best


def _materialize_split(node: TreeNode, candidate: SplitCandidate) -> None:
    node.is_leaf = False
    node.split_variable = candidate.variable
    node.split_kind = candidate.kind
    node.split_threshold = candidate.threshold
    node.split_left_values = candidate.left_values
    node.split_right_values = candidate.right_values


def _child_rules(node: TreeNode, df: pd.DataFrame, idx: pd.Index) -> list[BranchRule]:
    """Branch rules for a just-materialized split, including a 'missing'
    branch only when the node's population actually has missing values
    for the split variable."""
    rules: list[BranchRule] = []
    if node.split_kind == "numeric":
        rules.append(BranchRule(node.split_variable, "numeric", "<=", threshold=node.split_threshold))
        rules.append(BranchRule(node.split_variable, "numeric", ">", threshold=node.split_threshold))
    else:
        rules.append(BranchRule(node.split_variable, "categorical", "in", values=node.split_left_values))
        rules.append(BranchRule(node.split_variable, "categorical", "in", values=node.split_right_values))

    if df.loc[idx, node.split_variable].isna().any():
        kind = "numeric" if node.split_kind == "numeric" else "categorical"
        rules.append(BranchRule(node.split_variable, kind, "missing"))
    return rules


def node_row_index(df: pd.DataFrame, tree: DecisionTree, node_id: str) -> pd.Index:
    """Row index belonging to a node, by replaying its branch-rule chain
    from the root."""
    chain: list[BranchRule] = []
    node = tree.nodes[node_id]
    while node.branch_rule is not None:
        chain.append(node.branch_rule)
        node = tree.nodes[node.parent_id]

    idx = df.index
    for rule in reversed(chain):
        idx = idx[branch_mask(df.loc[idx], rule)]
    return idx


def leaf_rules_table(tree: DecisionTree) -> list[dict[str, Any]]:
    """One row per leaf: its full rule path from the root, stats, and
    assigned policy — the exportable "strategy table"."""
    rows = []
    for node in tree.nodes.values():
        if not node.is_leaf:
            continue
        path: list[str] = []
        cur = node
        while cur.branch_rule is not None:
            path.append(cur.branch_rule.describe())
            cur = tree.nodes[cur.parent_id]
        path.reverse()
        rows.append(
            {
                "node_id": node.id,
                "rule": " AND ".join(path) if path else "All records",
                "n_total": node.n_total,
                "n_bad": node.n_bad,
                "bad_rate_pct": node.bad_rate_pct,
                "policy": node.policy,
            }
        )
    rows.sort(key=lambda r: r["bad_rate_pct"], reverse=True)
    return rows


def build_tree(
    df: pd.DataFrame,
    bad_flag: pd.Series,
    candidate_vars: list[str],
    max_depth: int = 4,
    min_leaf_size_frac: float = 0.05,
    criterion: Criterion = "gini",
) -> DecisionTree:
    min_leaf_size = max(1, int(round(min_leaf_size_frac * len(bad_flag))))
    nodes: dict[str, TreeNode] = {}
    counter = 0

    def next_id() -> str:
        nonlocal counter
        node_id = f"n{counter}"
        counter += 1
        return node_id

    root_id = next_id()
    root = _make_node(root_id, None, 0, None, bad_flag)
    nodes[root_id] = root

    queue: list[tuple[str, pd.Index]] = [(root_id, df.index)]
    while queue:
        node_id, idx = queue.pop(0)
        node = nodes[node_id]
        if node.depth >= max_depth or node.n_total < 2 * min_leaf_size:
            continue

        candidate = find_best_split(df.loc[idx], bad_flag.loc[idx], candidate_vars, criterion, min_leaf_size)
        if candidate is None:
            continue

        _materialize_split(node, candidate)
        rules = _child_rules(node, df, idx)
        for rule in rules:
            child_idx = idx[branch_mask(df.loc[idx], rule)]
            if len(child_idx) == 0:
                continue
            child_id = next_id()
            child = _make_node(child_id, node_id, node.depth + 1, rule, bad_flag.loc[child_idx])
            nodes[child_id] = child
            node.children.append(child_id)
            queue.append((child_id, child_idx))

    return DecisionTree(root_id=root_id, nodes=nodes)
