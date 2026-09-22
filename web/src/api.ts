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

export interface ProjectDetail extends ProjectSummary {
  step_status: Record<string, StepStatus>;
  artifacts: Record<string, unknown> & { data_ingestion?: DataIngestionArtifact };
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
};
