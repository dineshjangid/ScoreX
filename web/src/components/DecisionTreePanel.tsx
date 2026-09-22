import { useState } from "react";
import { API_BASE, api } from "../api";
import type { ColumnProfile, DecisionTreeArtifact, LeafRuleRow, NodeSplitInput, ProjectDetail, TreeNode } from "../api";
import TreeDiagram from "./TreeDiagram";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

function SplitForm({
  columns,
  busy,
  onSubmit,
  onCancel,
}: {
  columns: ColumnProfile[];
  busy: boolean;
  onSubmit: (body: NodeSplitInput) => void;
  onCancel: () => void;
}) {
  const [variable, setVariable] = useState(columns[0]?.name ?? "");
  const col = columns.find((c) => c.name === variable);
  const isNumeric = col?.kind === "numeric";
  const [threshold, setThreshold] = useState("");
  const [leftValues, setLeftValues] = useState<Set<string>>(new Set());

  function handleVariableChange(name: string) {
    setVariable(name);
    setThreshold("");
    setLeftValues(new Set());
  }

  function handleSubmit() {
    if (isNumeric) {
      onSubmit({ variable, kind: "numeric", threshold: parseFloat(threshold) });
    } else {
      const all = (col?.distinct_values ?? []).map((v) => v.value);
      const right = all.filter((v) => !leftValues.has(v));
      onSubmit({ variable, kind: "categorical", left_values: Array.from(leftValues), right_values: right });
    }
  }

  const canSubmit = isNumeric ? threshold.trim() !== "" : leftValues.size > 0;

  return (
    <div className="bin-editor">
      <label>
        Variable
        <select value={variable} onChange={(e) => handleVariableChange(e.target.value)}>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.kind})
            </option>
          ))}
        </select>
      </label>

      {isNumeric ? (
        <label>
          Threshold (splits into &le; and &gt;)
          <input type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        </label>
      ) : col?.distinct_values ? (
        <div>
          <p className="muted">Check categories for the left branch; unchecked categories go to the right branch.</p>
          <div className="checkbox-list">
            {col.distinct_values.map((v) => (
              <label key={v.value} className="checkbox-item">
                <input
                  type="checkbox"
                  checked={leftValues.has(v.value)}
                  onChange={(e) => {
                    const next = new Set(leftValues);
                    if (e.target.checked) next.add(v.value);
                    else next.delete(v.value);
                    setLeftValues(next);
                  }}
                />
                {v.value} <span className="muted">({v.count})</span>
              </label>
            ))}
          </div>
        </div>
      ) : (
        <p className="muted">No distinct-value list available for this column (too many unique values).</p>
      )}

      <div className="button-row">
        <button type="button" onClick={handleSubmit} disabled={busy || !canSubmit}>
          Apply split
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function DecisionTreePanel({ project, onSaved }: Props) {
  const existing = project.artifacts.decision_tree;
  const [maxDepth, setMaxDepth] = useState(existing?.config?.max_depth ?? 4);
  const [minLeafFrac, setMinLeafFrac] = useState(existing?.config?.min_leaf_size_frac ?? 0.05);
  const [criterion, setCriterion] = useState<"gini" | "entropy">(existing?.config?.criterion ?? "gini");
  const [tree, setTree] = useState<DecisionTreeArtifact | null>(existing ?? null);
  const [selectedId, setSelectedId] = useState<string | null>(existing?.root_id ?? null);
  const [mode, setMode] = useState<"split" | "policy" | null>(null);
  const [policyDraft, setPolicyDraft] = useState("");
  const [rules, setRules] = useState<LeafRuleRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const samplingReady = project.step_status["sampling"] === "complete";
  const columns = project.artifacts.data_ingestion?.columns ?? [];

  async function refreshProject() {
    onSaved(await api.getProject(project.id));
  }

  async function handleBuild() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.buildDecisionTree(project.id, {
        variables: null,
        max_depth: maxDepth,
        min_leaf_size_frac: minLeafFrac,
        criterion,
      });
      setTree(result);
      setSelectedId(result.root_id);
      setMode(null);
      setRules(null);
      await refreshProject();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSplit(body: NodeSplitInput) {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.splitTreeNode(project.id, selectedId, body);
      setTree(result);
      setMode(null);
      setRules(null);
      await refreshProject();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePrune() {
    if (!selectedId) return;
    if (!window.confirm("Prune this node's subtree? This discards any splits/policies below it.")) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.pruneTreeNode(project.id, selectedId);
      setTree(result);
      setRules(null);
      await refreshProject();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSavePolicy() {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.setTreeNodePolicy(project.id, selectedId, policyDraft.trim() || null);
      setTree(result);
      setMode(null);
      await refreshProject();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadRules() {
    setError(null);
    try {
      setRules(await api.getTreeRules(project.id));
    } catch (err) {
      setError(String(err));
    }
  }

  if (!samplingReady) {
    return <p className="muted">Run sampling first.</p>;
  }

  const selectedNode: TreeNode | null = tree && selectedId ? tree.nodes[selectedId] ?? null : null;

  return (
    <div className="ingestion-panel">
      <label>
        Max depth
        <input type="number" min="1" max="10" value={maxDepth} onChange={(e) => setMaxDepth(parseInt(e.target.value, 10))} />
      </label>
      <label>
        Min leaf size (fraction of training sample)
        <input
          type="number"
          step="0.01"
          min="0.01"
          max="0.3"
          value={minLeafFrac}
          onChange={(e) => setMinLeafFrac(parseFloat(e.target.value))}
        />
      </label>
      <label>
        Splitting criterion
        <select value={criterion} onChange={(e) => setCriterion(e.target.value as "gini" | "entropy")}>
          <option value="gini">Gini impurity</option>
          <option value="entropy">Entropy</option>
        </select>
      </label>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleBuild} disabled={busy}>
          {tree ? "Rebuild tree" : "Build tree"}
        </button>
      </div>

      {tree && (
        <>
          <p className="muted">Click a node to select it, then split, prune, or assign a policy below.</p>
          <TreeDiagram
            nodes={tree.nodes}
            rootId={tree.root_id}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id);
              setMode(null);
            }}
          />

          {selectedNode && (
            <div className="node-detail">
              <p>
                <strong>{selectedNode.branch_rule ? selectedNode.branch_description : "All records"}</strong>
              </p>
              <p className="muted">
                N={selectedNode.n_total}, bad={selectedNode.n_bad} ({selectedNode.bad_rate_pct}%), good=
                {selectedNode.n_good}
              </p>

              <div className="button-row">
                {selectedNode.is_leaf ? (
                  <button type="button" onClick={() => setMode(mode === "split" ? null : "split")} disabled={busy}>
                    {mode === "split" ? "Cancel split" : "Split this node"}
                  </button>
                ) : (
                  <button className="danger" type="button" onClick={handlePrune} disabled={busy}>
                    Prune subtree
                  </button>
                )}
                {selectedNode.is_leaf && (
                  <button
                    type="button"
                    onClick={() => {
                      setPolicyDraft(selectedNode.policy ?? "");
                      setMode(mode === "policy" ? null : "policy");
                    }}
                    disabled={busy}
                  >
                    {mode === "policy" ? "Cancel" : "Assign policy"}
                  </button>
                )}
              </div>

              {mode === "split" && (
                <SplitForm columns={columns} busy={busy} onCancel={() => setMode(null)} onSubmit={handleSplit} />
              )}

              {mode === "policy" && (
                <div className="button-row">
                  <input
                    type="text"
                    value={policyDraft}
                    onChange={(e) => setPolicyDraft(e.target.value)}
                    placeholder="e.g. Approve, Decline, Refer"
                  />
                  <button type="button" onClick={handleSavePolicy} disabled={busy}>
                    Save policy
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="button-row">
            <button type="button" onClick={handleLoadRules}>
              {rules ? "Refresh strategy rules" : "Show strategy rules"}
            </button>
            <a className="button-like" href={`${API_BASE}/projects/${project.id}/decision_tree/export?format=python`} target="_blank" rel="noreferrer">
              Python export
            </a>
            <a className="button-like" href={`${API_BASE}/projects/${project.id}/decision_tree/export?format=sql`} target="_blank" rel="noreferrer">
              SQL export
            </a>
            <a className="button-like" href={`${API_BASE}/projects/${project.id}/decision_tree/export?format=csv`} target="_blank" rel="noreferrer">
              CSV export
            </a>
          </div>

          {rules && (
            <table className="profile-table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>N</th>
                  <th>Bad</th>
                  <th>Bad rate</th>
                  <th>Policy</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.node_id}>
                    <td>{r.rule}</td>
                    <td>{r.n_total}</td>
                    <td>{r.n_bad}</td>
                    <td>{r.bad_rate_pct}%</td>
                    <td>{r.policy ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
