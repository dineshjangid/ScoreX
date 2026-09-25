// Must share a host (not just resolve to the same machine) with the
// frontend origin for the session cookie to be sent: browsers treat
// "localhost" and "127.0.0.1" as different sites for SameSite=Lax
// cookie purposes, even though both point at loopback. In production
// (served by the same reverse proxy as the API — see DEPLOY.md) this
// defaults to a same-origin relative path; local dev keeps calling
// uvicorn directly on :8000 since Vite's dev server runs on a different
// port. Override at build time with VITE_API_BASE for any other shape.
export const API_BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "http://localhost:8000/api" : "/api");

export type ScorecardType = "application" | "behavioural" | "decision_tree";
export type StepStatus = "not_started" | "in_progress" | "complete";
export type UserRole = "analyst" | "validator" | "approver";

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
}

export interface AuditLogEntry {
  id: string;
  username: string;
  role: string;
  action: string;
  detail: string | null;
  created_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  scorecard_type: ScorecardType;
  created_at: string;
  updated_at: string;
}

export interface ChampionSummary {
  version_number: number;
  label: string | null;
  train_ks: number | null;
  train_gini: number | null;
}

export interface ProjectListItem extends ProjectSummary {
  steps_completed: number;
  steps_total: number;
  // First not-yet-complete step, or null once every step is complete.
  current_step: string | null;
  last_edited_by: string | null;
  champion: ChampionSummary | null;
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
  observation_date_column: string | null;
  performance_window_months: number | null;
}

export interface VintageRow {
  cohort: string;
  n_total: number;
  n_bad: number;
  bad_rate_pct: number;
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

export interface FinalModelCandidate {
  algorithm: string;
  train_auc: number;
  test_auc: number;
  train_gini: number;
  test_gini: number;
}

export interface FinalModelSelection {
  source: "logistic" | "ml_benchmark";
  algorithm: string;
  variables: string[];
  metrics: FinalModelCandidate | null;
}

export interface FinalModelStatus {
  current: FinalModelSelection | null;
  candidates: Record<string, FinalModelCandidate>;
}

export interface ScalingConfigInput {
  pdo: number;
  base_score: number;
  base_odds: number;
}

export interface BinPointsRow {
  label: string;
  woe: number;
  points: number;
}

export interface VariablePoints {
  variable: string;
  coefficient: number;
  bins: BinPointsRow[];
}

export interface ScoreDistribution {
  mean: number;
  std: number;
  min: number;
  p25: number;
  median: number;
  p75: number;
  max: number;
}

export interface Scorecard {
  factor: number;
  offset: number;
  base_points: number;
  variables: VariablePoints[];
  min_score: number;
  max_score: number;
  train_score_distribution: ScoreDistribution;
}

export interface ScalingArtifact extends Scorecard {
  config: ScalingConfigInput;
}

export interface ScalingNotApplicable {
  not_applicable: true;
  reason: string;
}

export interface SampleMetrics {
  n_total: number;
  n_bad: number;
  bad_rate_pct: number;
  ks: number;
  auc: number;
  gini: number;
}

export interface StabilityBucket {
  bucket: string;
  reference_pct: number;
  comparison_pct: number;
  contribution: number;
}

export interface StabilityResult {
  index: number;
  buckets: StabilityBucket[];
}

export interface DecileRow {
  score_range: string;
  n_total: number;
  n_bad: number;
  bad_rate_pct: number;
  pct_of_total_bad: number;
}

export interface RocPoint {
  fpr: number;
  tpr: number;
}

export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
}

export interface ValidationArtifact {
  train: SampleMetrics;
  test: SampleMetrics;
  oot: SampleMetrics | null;
  roc_train: RocPoint[];
  decile_table_train: DecileRow[];
  score_histogram_train?: HistogramBin[];
  psi_test_vs_train: StabilityResult;
  psi_oot_vs_train: StabilityResult | null;
  csi_test_vs_train: Record<string, StabilityResult>;
  csi_oot_vs_train: Record<string, StabilityResult> | null;
}

export interface ReasonCodesConfigInput {
  top_n: number;
  preview_rows: number;
}

export interface ReasonCodesArtifact {
  top_n: number;
  n_scored: number;
  preview: Record<string, unknown>[];
}

export interface BatchScoringResult {
  filename: string;
  n_scored: number;
  top_n: number;
  score_distribution: ScoreDistribution;
  preview: Record<string, unknown>[];
}

export interface BranchRule {
  variable: string;
  kind: "numeric" | "categorical";
  operator: "<=" | ">" | "missing" | "in" | "not_in";
  threshold: number | null;
  values: string[] | null;
}

export interface TreeNode {
  id: string;
  parent_id: string | null;
  depth: number;
  branch_rule: BranchRule | null;
  branch_description: string;
  n_total: number;
  n_bad: number;
  n_good: number;
  bad_rate_pct: number;
  is_leaf: boolean;
  split_variable: string | null;
  split_kind: "numeric" | "categorical" | null;
  split_threshold: number | null;
  split_left_values: string[] | null;
  split_right_values: string[] | null;
  children: string[];
  policy: string | null;
}

export interface DecisionTreeArtifact {
  config?: DecisionTreeConfigInput;
  root_id: string;
  nodes: Record<string, TreeNode>;
}

export interface DecisionTreeConfigInput {
  variables: string[] | null;
  max_depth: number;
  min_leaf_size_frac: number;
  criterion: "gini" | "entropy";
}

export interface NodeSplitInput {
  variable: string;
  kind: "numeric" | "categorical";
  threshold?: number | null;
  left_values?: string[] | null;
  right_values?: string[] | null;
}

export interface LeafRuleRow {
  node_id: string;
  rule: string;
  n_total: number;
  n_bad: number;
  bad_rate_pct: number;
  policy: string | null;
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
    final_model_selection?: FinalModelSelection;
    scaling?: ScalingArtifact | ScalingNotApplicable;
    validation?: ValidationArtifact;
    reason_codes?: ReasonCodesArtifact;
    ml_benchmark?: { config: MLBenchmarkConfigInput; results: Record<string, MLBenchmarkResult> };
    batch_scoring?: BatchScoringResult;
    decision_tree?: DecisionTreeArtifact;
  };
}

export interface ReportingStatus {
  status: string;
}

export interface VersionSummary {
  id: string;
  version_number: number;
  label: string | null;
  is_champion: boolean;
  created_at: string;
  n_variables: number;
  train_auc: number | null;
  train_ks: number | null;
  train_gini: number | null;
  score_range: string | null;
}

export interface VersionDetail extends VersionSummary {
  snapshot: {
    target_definition?: TargetArtifact;
    sampling?: SamplingArtifact;
    binning?: BinningArtifact;
    variable_selection?: SelectionArtifact;
    modeling?: ModelArtifact;
    final_model_selection?: FinalModelSelection;
    scaling?: ScalingArtifact | ScalingNotApplicable;
    validation?: ValidationArtifact;
    ml_benchmark?: { config: MLBenchmarkConfigInput; results: Record<string, MLBenchmarkResult> } | null;
  };
}

export type MLAlgorithm = "xgboost" | "random_forest" | "lightgbm" | "catboost";

export const ML_ALGORITHM_LABELS: Record<MLAlgorithm, string> = {
  xgboost: "XGBoost",
  random_forest: "Random Forest",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
};

export interface MLBenchmarkConfigInput {
  variables: string[] | null;
  n_estimators: number;
  max_depth: number;
  algorithm: MLAlgorithm | "all";
}

export interface FeatureImportance {
  variable: string;
  mean_abs_shap: number;
}

export interface MLBenchmarkResult {
  algorithm: string;
  variables: string[];
  train_auc: number;
  test_auc: number;
  train_gini: number;
  test_gini: number;
  feature_importance: FeatureImportance[];
}

export interface MLBenchmarkAllResult {
  results: Record<string, MLBenchmarkResult>;
}

export const STEP_ORDER = [
  "data_ingestion",
  "target_definition",
  "sampling",
  "binning",
  "variable_selection",
  "modeling",
  "final_model_selection",
  "scaling",
  "validation",
  "reason_codes",
  "reporting",
] as const;

// Decision Tree projects skip WOE binning/logistic regression/scaling
// entirely — the tree itself is the model and the deployable artifact.
export const DECISION_TREE_STEP_ORDER = ["data_ingestion", "target_definition", "sampling", "decision_tree"] as const;

export function stepOrderFor(scorecardType: ScorecardType): readonly string[] {
  return scorecardType === "decision_tree" ? DECISION_TREE_STEP_ORDER : STEP_ORDER;
}

export const STEP_LABELS: Record<string, string> = {
  data_ingestion: "Data Ingestion & Profiling",
  target_definition: "Target Definition",
  sampling: "Sampling",
  binning: "Binning & WOE/IV",
  variable_selection: "Variable Selection",
  modeling: "Model Building",
  final_model_selection: "Final Model Selection",
  scaling: "Scaling to Points",
  validation: "Validation",
  reason_codes: "Reason Codes",
  reporting: "Documentation & Export",
  decision_tree: "Decision Tree",
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listProjects: () => request<ProjectListItem[]>("/projects"),
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
      credentials: "include",
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
  getVintageAnalysis: (projectId: string, dateColumn?: string) =>
    request<VintageRow[]>(
      `/projects/${projectId}/target/vintage${dateColumn ? `?date_column=${encodeURIComponent(dateColumn)}` : ""}`
    ),
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
  editBinning: (
    projectId: string,
    variable: string,
    body: { cutpoints?: number[] | null; categories_map?: Record<string, string> | null }
  ) =>
    request<BinningSummaryItem>(`/projects/${projectId}/binning/${encodeURIComponent(variable)}`, {
      method: "PUT",
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
  getFinalModelStatus: (projectId: string) => request<FinalModelStatus>(`/projects/${projectId}/final_model`),
  setFinalModel: (projectId: string, algorithm: string) =>
    request<FinalModelSelection>(`/projects/${projectId}/final_model`, {
      method: "POST",
      body: JSON.stringify({ algorithm }),
    }),
  runScaling: (projectId: string, body: ScalingConfigInput) =>
    request<Scorecard>(`/projects/${projectId}/scaling`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runValidation: (projectId: string) =>
    request<ValidationArtifact>(`/projects/${projectId}/validation`, { method: "POST" }),
  runReasonCodes: (projectId: string, body: ReasonCodesConfigInput) =>
    request<ReasonCodesArtifact>(`/projects/${projectId}/reason_codes`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  completeReporting: (projectId: string) =>
    request<ReportingStatus>(`/projects/${projectId}/reporting`, { method: "POST" }),
  runMlBenchmark: (projectId: string, body: MLBenchmarkConfigInput) =>
    request<MLBenchmarkAllResult>(`/projects/${projectId}/ml_benchmark`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  uploadBatch: async (projectId: string, file: File, topN: number): Promise<BatchScoringResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/projects/${projectId}/batch_scoring?top_n=${topN}`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<BatchScoringResult>;
  },
  createVersion: (projectId: string, label: string | null) =>
    request<VersionSummary>(`/projects/${projectId}/versions`, {
      method: "POST",
      body: JSON.stringify({ label }),
    }),
  listVersions: (projectId: string) => request<VersionSummary[]>(`/projects/${projectId}/versions`),
  getVersion: (projectId: string, versionId: string) =>
    request<VersionDetail>(`/projects/${projectId}/versions/${versionId}`),
  setChampion: (projectId: string, versionId: string) =>
    request<VersionSummary>(`/projects/${projectId}/versions/${versionId}/champion`, { method: "POST" }),
  deleteVersion: (projectId: string, versionId: string) =>
    request<void>(`/projects/${projectId}/versions/${versionId}`, { method: "DELETE" }),
  buildDecisionTree: (projectId: string, body: DecisionTreeConfigInput) =>
    request<DecisionTreeArtifact>(`/projects/${projectId}/decision_tree`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  splitTreeNode: (projectId: string, nodeId: string, body: NodeSplitInput) =>
    request<DecisionTreeArtifact>(`/projects/${projectId}/decision_tree/nodes/${nodeId}/split`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  pruneTreeNode: (projectId: string, nodeId: string) =>
    request<DecisionTreeArtifact>(`/projects/${projectId}/decision_tree/nodes/${nodeId}/prune`, { method: "POST" }),
  setTreeNodePolicy: (projectId: string, nodeId: string, policy: string | null) =>
    request<DecisionTreeArtifact>(`/projects/${projectId}/decision_tree/nodes/${nodeId}/policy`, {
      method: "PUT",
      body: JSON.stringify({ policy }),
    }),
  getTreeRules: (projectId: string) => request<LeafRuleRow[]>(`/projects/${projectId}/decision_tree/rules`),
  getMe: () => request<AuthUser>("/auth/me"),
  getAuthConfig: () => request<{ saml_enabled: boolean }>("/auth/config"),
  login: (username: string, password: string) =>
    request<AuthUser>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  register: (username: string, password: string, role: UserRole) =>
    request<AuthUser>("/auth/register", { method: "POST", body: JSON.stringify({ username, password, role }) }),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  getAuditLog: (projectId: string) => request<AuditLogEntry[]>(`/projects/${projectId}/audit`),
};
