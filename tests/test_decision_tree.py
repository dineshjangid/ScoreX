import numpy as np
import pandas as pd
import pytest

from credittool_engine.decision_tree import (
    build_tree,
    generate_tree_python,
    generate_tree_sql,
    leaf_rules_table,
    node_row_index,
    prune_node,
    set_policy,
    split_node_categorical,
    split_node_numeric,
)


def _synthetic_df(n=1000, seed=0):
    rng = np.random.default_rng(seed)
    income = rng.uniform(0, 100000, n)
    segment = rng.choice(["A", "B", "C"], n)
    segment_risk = np.where(segment == "C", 0.3, np.where(segment == "B", 0.0, -0.3))
    logit_bad = -0.00003 * (income - 50000) + segment_risk
    p_bad = 1 / (1 + np.exp(-logit_bad))
    bad = pd.Series((rng.uniform(size=n) < p_bad).astype(float))
    df = pd.DataFrame({"income": income, "segment": segment})
    return df, bad


def test_build_tree_every_row_assigned_to_exactly_one_leaf():
    df, bad = _synthetic_df()
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=3, min_leaf_size_frac=0.05)

    leaves = [n for n in tree.nodes.values() if n.is_leaf]
    assert sum(leaf.n_total for leaf in leaves) == len(df)

    # every row's index recomputed from each leaf should be disjoint and total to n
    all_idx = set()
    for leaf in leaves:
        idx = node_row_index(df, tree, leaf.id)
        assert len(idx) == leaf.n_total
        assert not (all_idx & set(idx))
        all_idx.update(idx)
    assert len(all_idx) == len(df)


def test_build_tree_respects_min_leaf_size():
    df, bad = _synthetic_df(n=2000)
    min_frac = 0.1
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=4, min_leaf_size_frac=min_frac)
    min_size = int(min_frac * len(df))
    for node in tree.nodes.values():
        if node.is_leaf:
            assert node.n_total >= 1  # leaves from a valid split are always >= min_leaf_size by construction
    # no internal split created a child smaller than the minimum
    for node in tree.nodes.values():
        if not node.is_leaf:
            for child_id in node.children:
                child = tree.nodes[child_id]
                if child.branch_rule and child.branch_rule.operator != "missing":
                    assert child.n_total >= min_size


def test_build_tree_respects_max_depth():
    df, bad = _synthetic_df(n=3000)
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=2, min_leaf_size_frac=0.01)
    assert max(n.depth for n in tree.nodes.values()) <= 2


def test_build_tree_splits_on_informative_variable():
    df, bad = _synthetic_df(n=3000)
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=1, min_leaf_size_frac=0.05)
    root = tree.nodes[tree.root_id]
    assert not root.is_leaf
    assert root.split_variable in ("income", "segment")


def test_manual_numeric_split_creates_correct_children():
    df, bad = _synthetic_df(n=500)
    tree = build_tree(df, bad, candidate_vars=["income"], max_depth=0, min_leaf_size_frac=0.05)
    root_id = tree.root_id
    assert tree.nodes[root_id].is_leaf  # max_depth=0 -> root stays a leaf

    split_node_numeric(df, bad, tree, root_id, "income", 50000.0)
    root = tree.nodes[root_id]
    assert not root.is_leaf
    assert len(root.children) == 2  # no missing values in synthetic income

    left = tree.nodes[root.children[0]]
    right = tree.nodes[root.children[1]]
    assert left.n_total + right.n_total == len(df)

    left_idx = node_row_index(df, tree, left.id)
    assert (df.loc[left_idx, "income"] <= 50000.0).all()


def test_manual_categorical_split_creates_correct_children():
    df, bad = _synthetic_df(n=500)
    tree = build_tree(df, bad, candidate_vars=["segment"], max_depth=0, min_leaf_size_frac=0.05)
    root_id = tree.root_id

    split_node_categorical(df, bad, tree, root_id, "segment", left_values=["A"], right_values=["B", "C"])
    root = tree.nodes[root_id]
    assert not root.is_leaf

    left = tree.nodes[root.children[0]]
    left_idx = node_row_index(df, tree, left.id)
    assert (df.loc[left_idx, "segment"] == "A").all()


def test_split_on_already_split_node_raises():
    df, bad = _synthetic_df(n=500)
    tree = build_tree(df, bad, candidate_vars=["income"], max_depth=2, min_leaf_size_frac=0.05)
    root_id = tree.root_id
    assert not tree.nodes[root_id].is_leaf
    with pytest.raises(ValueError, match="already split"):
        split_node_numeric(df, bad, tree, root_id, "income", 10000.0)


def test_prune_removes_descendants_and_restores_leaf():
    df, bad = _synthetic_df(n=1000)
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=3, min_leaf_size_frac=0.05)
    root_id = tree.root_id
    n_before = len(tree.nodes)
    assert n_before > 1

    prune_node(tree, root_id)
    root = tree.nodes[root_id]
    assert root.is_leaf
    assert root.children == []
    assert len(tree.nodes) == 1


def test_set_policy_on_leaf_and_rejects_internal_node():
    df, bad = _synthetic_df(n=500)
    tree = build_tree(df, bad, candidate_vars=["income"], max_depth=2, min_leaf_size_frac=0.05)
    leaf = next(n for n in tree.nodes.values() if n.is_leaf)
    set_policy(tree, leaf.id, "Approve")
    assert tree.nodes[leaf.id].policy == "Approve"

    internal = next(n for n in tree.nodes.values() if not n.is_leaf)
    with pytest.raises(ValueError, match="leaf"):
        set_policy(tree, internal.id, "Decline")


def test_leaf_rules_table_covers_all_leaves_and_sums_to_total():
    df, bad = _synthetic_df(n=800)
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=3, min_leaf_size_frac=0.05)
    rows = leaf_rules_table(tree)
    n_leaves = sum(1 for n in tree.nodes.values() if n.is_leaf)
    assert len(rows) == n_leaves
    assert sum(r["n_total"] for r in rows) == len(df)
    for r in rows:
        assert "rule" in r and isinstance(r["rule"], str)


def _assign_policies_by_bad_rate(tree):
    for node in tree.nodes.values():
        if node.is_leaf:
            node.policy = "Decline" if node.bad_rate_pct > 20 else "Approve"


def test_generated_python_matches_actual_leaf_membership():
    df, bad = _synthetic_df(n=600)
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=3, min_leaf_size_frac=0.05)
    _assign_policies_by_bad_rate(tree)

    code = generate_tree_python(tree.to_dict())
    namespace: dict = {}
    exec(code, namespace)
    classify = namespace["classify"]

    for node in tree.nodes.values():
        if not node.is_leaf:
            continue
        idx = node_row_index(df, tree, node.id)
        if len(idx) == 0:
            continue
        sample_row = df.loc[idx[0]].to_dict()
        assert classify(sample_row) == node.policy


def test_generated_sql_has_one_when_per_leaf_and_covers_variables():
    df, bad = _synthetic_df(n=600)
    tree = build_tree(df, bad, candidate_vars=["income", "segment"], max_depth=2, min_leaf_size_frac=0.05)
    _assign_policies_by_bad_rate(tree)

    sql = generate_tree_sql(tree.to_dict(), table="loans")
    n_leaves = sum(1 for n in tree.nodes.values() if n.is_leaf)
    assert sql.count("WHEN") == n_leaves
    assert "FROM loans" in sql
    assert "income" in sql or "segment" in sql
