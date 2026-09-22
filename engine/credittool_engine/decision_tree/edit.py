"""Interactive tree editing: manually split a leaf (overriding the
automatic search), prune a subtree back to a leaf, or assign a policy
label to a leaf — the Angoss/RapidMiner-style "build then adjust by
hand" workflow.
"""
from __future__ import annotations

import pandas as pd

from .rules import BranchRule, branch_mask
from .tree import DecisionTree, TreeNode, _child_rules, _make_node, node_row_index


def _next_node_id(tree: DecisionTree) -> str:
    existing = [int(node_id[1:]) for node_id in tree.nodes if node_id[1:].isdigit()]
    return f"n{max(existing, default=-1) + 1}"


def _attach_children(
    tree: DecisionTree, df: pd.DataFrame, bad_flag: pd.Series, node: TreeNode, idx: pd.Index, rules: list[BranchRule]
) -> None:
    node.children = []
    for rule in rules:
        child_idx = idx[branch_mask(df.loc[idx], rule)]
        if len(child_idx) == 0:
            continue
        child_id = _next_node_id(tree)
        child = _make_node(child_id, node.id, node.depth + 1, rule, bad_flag.loc[child_idx])
        tree.nodes[child_id] = child
        node.children.append(child_id)


def split_node_numeric(df: pd.DataFrame, bad_flag: pd.Series, tree: DecisionTree, node_id: str, variable: str, threshold: float) -> None:
    node = tree.nodes[node_id]
    if not node.is_leaf:
        raise ValueError("Node is already split — prune it first")
    idx = node_row_index(df, tree, node_id)

    node.split_variable = variable
    node.split_kind = "numeric"
    node.split_threshold = threshold
    node.split_left_values = None
    node.split_right_values = None
    node.is_leaf = False

    _attach_children(tree, df, bad_flag, node, idx, _child_rules(node, df, idx))


def split_node_categorical(
    df: pd.DataFrame, bad_flag: pd.Series, tree: DecisionTree, node_id: str, variable: str, left_values: list[str], right_values: list[str]
) -> None:
    node = tree.nodes[node_id]
    if not node.is_leaf:
        raise ValueError("Node is already split — prune it first")
    idx = node_row_index(df, tree, node_id)

    node.split_variable = variable
    node.split_kind = "categorical"
    node.split_threshold = None
    node.split_left_values = left_values
    node.split_right_values = right_values
    node.is_leaf = False

    _attach_children(tree, df, bad_flag, node, idx, _child_rules(node, df, idx))


def prune_node(tree: DecisionTree, node_id: str) -> None:
    """Collapse node_id's subtree back into a leaf, discarding descendants."""
    node = tree.nodes[node_id]
    if node.is_leaf:
        return

    stack = list(node.children)
    while stack:
        child_id = stack.pop()
        child = tree.nodes.pop(child_id, None)
        if child:
            stack.extend(child.children)

    node.children = []
    node.is_leaf = True
    node.split_variable = None
    node.split_kind = None
    node.split_threshold = None
    node.split_left_values = None
    node.split_right_values = None


def set_policy(tree: DecisionTree, node_id: str, policy: str | None) -> None:
    node = tree.nodes[node_id]
    if not node.is_leaf:
        raise ValueError("A policy can only be assigned to a leaf node")
    node.policy = policy
