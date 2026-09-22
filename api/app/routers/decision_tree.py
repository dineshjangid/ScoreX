from __future__ import annotations

import io
import os

import pandas as pd
from fastapi import APIRouter, HTTPException, Response

from credittool_engine.data import load_dataframe
from credittool_engine.decision_tree import (
    DecisionTree,
    build_tree,
    generate_tree_python,
    generate_tree_sql,
    leaf_rules_table,
)
from credittool_engine.decision_tree import prune_node as engine_prune_node
from credittool_engine.decision_tree import set_policy as engine_set_policy
from credittool_engine.decision_tree import split_node_categorical, split_node_numeric
from credittool_engine.project import StepName, StepStatus

from ..db import ProjectRecord, get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import DecisionTreeConfigIn, DecisionTreeOut, LeafRuleOut, NodePolicyIn, NodeSplitIn

router = APIRouter(prefix="/api/projects/{project_id}/decision_tree", tags=["decision_tree"])


def _load_train(record: ProjectRecord) -> tuple[pd.DataFrame, pd.Series]:
    if not record.data_path or not os.path.exists(record.data_path):
        raise HTTPException(status_code=400, detail="Upload a dataset first")
    if not record.splits_path or not os.path.exists(record.splits_path):
        raise HTTPException(status_code=400, detail="Run sampling before building a decision tree")
    df = load_dataframe(record.data_path)
    splits = pd.read_parquet(record.splits_path)
    train_idx = splits.index[splits["sample"] == "train"]
    if len(train_idx) == 0:
        raise HTTPException(status_code=400, detail="Training sample is empty; adjust sampling first")
    return df.loc[train_idx], splits.loc[train_idx, "target"]


def _tree_from_artifact(tree_artifact: dict) -> DecisionTree:
    return DecisionTree.from_dict({"root_id": tree_artifact["root_id"], "nodes": tree_artifact["nodes"]})


@router.post("", response_model=DecisionTreeOut)
def build(project_id: str, body: DecisionTreeConfigIn) -> DecisionTreeOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        target_artifact = project.artifacts.get(StepName.TARGET_DEFINITION.value)
        if not target_artifact:
            raise HTTPException(status_code=400, detail="Define the target before building a decision tree")

        train_df, train_bad = _load_train(record)

        definition = target_artifact["definition"]
        skip_columns = {definition["target_column"]}
        if definition.get("exclude_column"):
            skip_columns.add(definition["exclude_column"])

        candidate_vars = body.variables or [c for c in train_df.columns if c not in skip_columns]
        missing = [v for v in candidate_vars if v not in train_df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown column(s): {missing}")

        tree = build_tree(
            train_df,
            train_bad,
            candidate_vars,
            max_depth=body.max_depth,
            min_leaf_size_frac=body.min_leaf_size_frac,
            criterion=body.criterion,
        )

        project.set_artifact(StepName.DECISION_TREE, {"config": body.model_dump(), **tree.to_dict()})
        project.mark_step(StepName.DECISION_TREE, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.DECISION_TREE)
        save_project(session, record, project)

    return DecisionTreeOut(**tree.to_dict())


@router.put("/nodes/{node_id}/split", response_model=DecisionTreeOut)
def split(project_id: str, node_id: str, body: NodeSplitIn) -> DecisionTreeOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        tree_artifact = project.artifacts.get(StepName.DECISION_TREE.value)
        if not tree_artifact:
            raise HTTPException(status_code=400, detail="Build a decision tree first")

        tree = _tree_from_artifact(tree_artifact)
        if node_id not in tree.nodes:
            raise HTTPException(status_code=404, detail="Node not found")

        train_df, train_bad = _load_train(record)
        try:
            if body.kind == "numeric":
                if body.threshold is None:
                    raise HTTPException(status_code=400, detail="threshold is required for a numeric split")
                split_node_numeric(train_df, train_bad, tree, node_id, body.variable, body.threshold)
            else:
                if not body.left_values or not body.right_values:
                    raise HTTPException(
                        status_code=400, detail="left_values and right_values are required for a categorical split"
                    )
                split_node_categorical(train_df, train_bad, tree, node_id, body.variable, body.left_values, body.right_values)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        project.set_artifact(StepName.DECISION_TREE, {"config": tree_artifact.get("config", {}), **tree.to_dict()})
        invalidate_downstream(project, record, StepName.DECISION_TREE)
        save_project(session, record, project)

    return DecisionTreeOut(**tree.to_dict())


@router.post("/nodes/{node_id}/prune", response_model=DecisionTreeOut)
def prune(project_id: str, node_id: str) -> DecisionTreeOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        tree_artifact = project.artifacts.get(StepName.DECISION_TREE.value)
        if not tree_artifact:
            raise HTTPException(status_code=400, detail="Build a decision tree first")

        tree = _tree_from_artifact(tree_artifact)
        if node_id not in tree.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        engine_prune_node(tree, node_id)

        project.set_artifact(StepName.DECISION_TREE, {"config": tree_artifact.get("config", {}), **tree.to_dict()})
        invalidate_downstream(project, record, StepName.DECISION_TREE)
        save_project(session, record, project)

    return DecisionTreeOut(**tree.to_dict())


@router.put("/nodes/{node_id}/policy", response_model=DecisionTreeOut)
def set_node_policy(project_id: str, node_id: str, body: NodePolicyIn) -> DecisionTreeOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        tree_artifact = project.artifacts.get(StepName.DECISION_TREE.value)
        if not tree_artifact:
            raise HTTPException(status_code=400, detail="Build a decision tree first")

        tree = _tree_from_artifact(tree_artifact)
        if node_id not in tree.nodes:
            raise HTTPException(status_code=404, detail="Node not found")
        try:
            engine_set_policy(tree, node_id, body.policy)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Assigning a policy doesn't change the tree's structure/stats, so
        # nothing downstream needs invalidating.
        project.set_artifact(StepName.DECISION_TREE, {"config": tree_artifact.get("config", {}), **tree.to_dict()})
        save_project(session, record, project)

    return DecisionTreeOut(**tree.to_dict())


@router.get("/rules", response_model=list[LeafRuleOut])
def rules(project_id: str) -> list[LeafRuleOut]:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        tree_artifact = project.artifacts.get(StepName.DECISION_TREE.value)
        if not tree_artifact:
            raise HTTPException(status_code=400, detail="Build a decision tree first")
        tree = _tree_from_artifact(tree_artifact)
        return [LeafRuleOut(**r) for r in leaf_rules_table(tree)]


@router.get("/export")
def export(project_id: str, format: str = "python", table: str = "applicants") -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        tree_artifact = project.artifacts.get(StepName.DECISION_TREE.value)
        if not tree_artifact:
            raise HTTPException(status_code=400, detail="Build a decision tree first")
        tree_dict = {"root_id": tree_artifact["root_id"], "nodes": tree_artifact["nodes"]}

    if format == "python":
        content = generate_tree_python(tree_dict)
        return Response(
            content=content, media_type="text/x-python", headers={"Content-Disposition": "attachment; filename=classify_strategy.py"}
        )
    if format == "sql":
        content = generate_tree_sql(tree_dict, table=table)
        return Response(
            content=content, media_type="text/plain", headers={"Content-Disposition": "attachment; filename=strategy_policy.sql"}
        )
    if format == "csv":
        rows = leaf_rules_table(DecisionTree.from_dict(tree_dict))
        buffer = io.StringIO()
        pd.DataFrame(rows).to_csv(buffer, index=False)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=strategy_tree_rules.csv"},
        )
    raise HTTPException(status_code=400, detail="format must be 'python', 'sql', or 'csv'")
