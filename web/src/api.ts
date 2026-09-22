const API_BASE = "http://127.0.0.1:8000/api";

export type ScorecardType = "application" | "behavioural";
export type StepStatus = "not_started" | "in_progress" | "complete";

export interface ProjectSummary {
  id: string;
  name: string;
  scorecard_type: ScorecardType;
  created_at: string;
  updated_at: string;
}

export interface ColumnProfile {
  name: string;
  kind: "numeric" | "categorical" | "boolean" | "datetime";
  count: number;
  missing_count: number;
  missing_pct: number;
  n_unique: number;
  stats?: {
    mean: number;
    std: number;
    min: number;
    p25: number;
    median: number;
    p75: number;
    max: number;
  };
  top_values?: { value: string; count: number; pct: number }[];
  distinct_values?: { value: string; count: number }[];
}

export interface DataIngestionArtifact {
  original_filename: string;
  n_rows: number;
  n_columns: number;
  columns: ColumnProfile[];
}

export interface DataPreview {
  columns: string[];
  rows: Record<string, unknown>[];
}

export type TargetMode = "values" | "threshold";

export interface TargetDefinitionInput {
  target_column: string;
  mode: TargetMode;
  bad_values: string[];
  threshold: number | null;
  exclude_values: string[];
  exclude_column: string | null;
}

export interface TargetSummary {
  n_total: number;
  n_good: number;
  n_bad: number;
  n_excluded: number;
  bad_rate_pct: number;
}

export interface SamplingConfigInput {
  test_size: number;
  oot_size: number;
  date_column: string | null;
  random_state: number;
}

export interface SampleGroupSummary {
  n_total: number;
  n_good: number;
  n_bad: number;
  bad_rate_pct: number;
}

export interface SamplingSummary {
  train: SampleGroupSummary;
  test: SampleGroupSummary;
  oot: SampleGroupSummary;
  excluded: SampleGroupSummary;
}

export interface TargetArtifact {
  definition: TargetDefinitionInput;
  summary: TargetSummary;
}

export interface SamplingArtifact {
  config: SamplingConfigInput;
  summary: SamplingSummary;
}

export interface BinningConfigInput {
  max_bins: number;
  min_bin_size: number;
  variables: string[] | null;
}

export interface BinRow {
  label: string;
  n_total: number;
  n_good: number;
  n_bad: number;
  bad_rate_pct: number;
  pct_of_total: number;
  woe: number;
}

export interface VariableBinning {
  variable: string;
  kind: "numeric" | "categorical";
  iv: number;
  bins: BinRow[];
  cutpoints: number[] | null;
  categories_map: Record<string, string> | null;
}

export interface BinningSummaryItem {
  variable: string;
  kind: "numeric" | "categorical";
  iv: number;
  n_bins: number;
}

export interface BinningArtifact {
  config: BinningConfigInput;
  variables: Record<string, VariableBinning>;
}

export interface SelectionConfigInput {
  min_iv: number;
  max_corr: number;
  max_vif: number;
}

export interface DroppedVariable {
  variable: string;
  reason: string;
}

export interface SelectionResult {
  selected: string[];
  dropped: DroppedVariable[];
  correlation_matrix: Record<string, Record<string, number>>;
  vif: Record<string, number>;
}

export interface SelectionArtifact extends SelectionResult {
  config: SelectionConfigInput;
}

export interface ModelingConfigInput {
  variables: string[] | null;
}

export interface CoefficientRow {
  variable: string;
  coefficient: number;
  std_error: number;
  p_value: number;
  z_value: number;
}

export interface ModelArtifact {
  variables: string[];
  intercept: number;
  coefficients: CoefficientRow[];
  n_obs: number;
  log_likelihood: number;
  pseudo_r2: number;
  aic: number;
  fitted_params: Record<string, number>;
}

export interface ProjectDetail extends ProjectSummary {
  step_status: Record<string, StepStatus>;
  artifacts: Record<string, unknown> & {
    data_ingestion?: DataIngestionArtifact;
    target_definition?: TargetArtifact;
    sampling?: SamplingArtifact;
    binning?: BinningArtifact;
    variable_selection?: SelectionArtifact;
    modeling?: ModelArtifact;
  };
}

export const STEP_ORDER = [
  "data_ingestion",
  "target_definition",
  "sampling",
  "binning",
  "variable_selection",
  "modeling",
  "scaling",
  "validation",
  "reason_codes",
  "reporting",
] as const;

export const STEP_LABELS: Record<string, string> = {
  data_ingestion: "Data Ingestion & Profiling",
  target_definition: "Target Definition",
  sampling: "Sampling",
  binning: "Binning & WOE/IV",
  variable_selection: "Variable Selection",
  modeling: "Model Building",
  scaling: "Scaling to Points",
  validation: "Validation",
  reason_codes: "Reason Codes",
  reporting: "Documentation & Export",
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (name: string, scorecard_type: ScorecardType) =>
    request<ProjectDetail>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, scorecard_type }),
    }),
  getProject: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  uploadData: async (projectId: string, file: File): Promise<ProjectDetail> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/projects/${projectId}/data`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<ProjectDetail>;
  },
  getDataPreview: (projectId: string, n = 20) =>
    request<DataPreview>(`/projects/${projectId}/data/preview?n=${n}`),
  previewTarget: (projectId: string, body: TargetDefinitionInput) =>
    request<TargetSummary>(`/projects/${projectId}/target/preview`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveTarget: (projectId: string, body: TargetDefinitionInput) =>
    request<TargetSummary>(`/projects/${projectId}/target`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  saveSampling: (projectId: string, body: SamplingConfigInput) =>
    request<SamplingSummary>(`/projects/${projectId}/sampling`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runBinning: (projectId: string, body: BinningConfigInput) =>
    request<BinningSummaryItem[]>(`/projects/${projectId}/binning`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runSelection: (projectId: string, body: SelectionConfigInput) =>
    request<SelectionResult>(`/projects/${projectId}/selection`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runModeling: (projectId: string, body: ModelingConfigInput) =>
    request<ModelArtifact>(`/projects/${projectId}/modeling`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
