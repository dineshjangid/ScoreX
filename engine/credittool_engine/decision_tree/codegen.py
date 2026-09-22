"""Generate standalone classifier code (Python function / SQL CASE
expression) from a finished decision tree — no dependency on this
package, for dropping into an external policy/rules engine.

Operates on the plain dict shape from DecisionTree.to_dict() /
TreeNode.to_dict() (as loaded from a JSON artifact), not the dataclasses.
"""
from __future__ import annotations


def generate_tree_python(tree: dict) -> str:
    lines = [
        "def classify(record: dict):",
        '    """Auto-generated decision tree classifier. Returns the leaf policy, or None if unclassified/unmatched."""',
    ]
    lines.extend(_node_code(tree["nodes"], tree["root_id"], indent=1))
    return "\n".join(lines)


def _condition_code(rule: dict) -> str:
    var = rule["variable"]
    if rule["kind"] == "numeric":
        if rule["operator"] == "missing":
            return f"record.get({var!r}) is None"
        return f"record.get({var!r}) is not None and record.get({var!r}) {rule['operator']} {rule['threshold']}"

    if rule["operator"] == "missing":
        return f"record.get({var!r}) is None"
    verb = "in" if rule["operator"] == "in" else "not in"
    return f"record.get({var!r}) is not None and str(record.get({var!r})) {verb} {set(rule['values'])!r}"


def _node_code(nodes: dict, node_id: str, indent: int) -> list[str]:
    node = nodes[node_id]
    pad = "    " * indent
    if node["is_leaf"]:
        return [f"{pad}return {node['policy']!r}"]

    lines = []
    for i, child_id in enumerate(node["children"]):
        rule = nodes[child_id]["branch_rule"]
        keyword = "if" if i == 0 else "elif"
        lines.append(f"{pad}{keyword} {_condition_code(rule)}:")
        lines.extend(_node_code(nodes, child_id, indent + 1))
    lines.append(f"{pad}else:")
    lines.append(f"{pad}    return None")
    return lines


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_condition(rule: dict) -> str:
    var = rule["variable"]
    if rule["kind"] == "numeric":
        if rule["operator"] == "missing":
            return f"{var} IS NULL"
        return f"{var} {rule['operator']} {rule['threshold']}"

    if rule["operator"] == "missing":
        return f"{var} IS NULL"
    quoted = ", ".join(_sql_quote(v) for v in rule["values"])
    verb = "IN" if rule["operator"] == "in" else "NOT IN"
    return f"{var} {verb} ({quoted})"


def generate_tree_sql(tree: dict, table: str = "applicants") -> str:
    nodes = tree["nodes"]
    when_lines = []
    for node in nodes.values():
        if not node["is_leaf"]:
            continue
        chain = []
        cur = node
        while cur.get("parent_id") is not None:
            chain.append(cur["branch_rule"])
            cur = nodes[cur["parent_id"]]
        chain.reverse()
        condition = " AND ".join(_sql_condition(r) for r in chain) if chain else "1=1"
        policy_sql = _sql_quote(node["policy"]) if node.get("policy") else "NULL"
        when_lines.append(f"  WHEN ({condition}) THEN {policy_sql}")

    case_expr = "CASE\n" + "\n".join(when_lines) + "\n  ELSE NULL\nEND"
    return f"SELECT *,\n  {case_expr} AS policy\nFROM {table};"
