import { useState } from "react";
import { api } from "../api";
import type { BinningSummaryItem, VariableBinning } from "../api";

interface Props {
  projectId: string;
  detail: VariableBinning;
  onSaved: (result: BinningSummaryItem) => void;
  onCancel: () => void;
}

export default function BinEditor({ projectId, detail, onSaved, onCancel }: Props) {
  const [cutpointsText, setCutpointsText] = useState((detail.cutpoints ?? []).join(", "));
  const [categoryDrafts, setCategoryDrafts] = useState<Record<string, string>>(detail.categories_map ?? {});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    setBusy(true);
    setError(null);
    try {
      let result: BinningSummaryItem;
      if (detail.kind === "numeric") {
        const cutpoints = cutpointsText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
          .map(Number);
        if (cutpoints.some((n) => Number.isNaN(n))) {
          throw new Error("Cutpoints must be a comma-separated list of numbers");
        }
        result = await api.editBinning(projectId, detail.variable, { cutpoints });
      } else {
        result = await api.editBinning(projectId, detail.variable, { categories_map: categoryDrafts });
      }
      onSaved(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bin-editor">
      <p className="muted">
        {detail.kind === "numeric"
          ? "Edit the cutpoints (comma-separated, ascending). Fewer cutpoints merges bins; more splits them."
          : "Edit which group each raw category belongs to. Categories with the same group name are merged into one bin."}
      </p>

      {detail.kind === "numeric" ? (
        <label>
          Cutpoints
          <input type="text" value={cutpointsText} onChange={(e) => setCutpointsText(e.target.value)} placeholder="e.g. 25, 40, 55" />
        </label>
      ) : (
        <div className="category-grid">
          {Object.entries(categoryDrafts).map(([raw, group]) => (
            <label key={raw}>
              {raw}
              <input
                type="text"
                value={group}
                onChange={(e) => setCategoryDrafts({ ...categoryDrafts, [raw]: e.target.value })}
              />
            </label>
          ))}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleSave} disabled={busy}>
          Save bins
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
}
