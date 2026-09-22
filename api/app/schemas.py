from __future__ import annotations

from pydantic import BaseModel

from credittool_engine.project import ScorecardType, StepStatus
from credittool_engine.target import TargetMode


class ProjectCreate(BaseModel):
    name: str
    scorecard_type: ScorecardType


class ProjectSummary(BaseModel):
    id: str
    name: str
    scorecard_type: ScorecardType
    created_at: str
    updated_at: str


class ProjectDetail(ProjectSummary):
    step_status: dict[str, StepStatus]
    artifacts: dict


class DataPreview(BaseModel):
    columns: list[str]
    rows: list[dict]


class TargetDefinitionIn(BaseModel):
    target_column: str
    mode: TargetMode
    bad_values: list[str] = []
    threshold: float | None = None
    exclude_values: list[str] = []
    exclude_column: str | None = None


class TargetSummary(BaseModel):
    n_total: int
    n_good: int
    n_bad: int
    n_excluded: int
    bad_rate_pct: float


class SamplingConfigIn(BaseModel):
    test_size: float = 0.3
    oot_size: float = 0.0
    date_column: str | None = None
    random_state: int = 42


class SampleGroupSummary(BaseModel):
    n_total: int
    n_good: int
    n_bad: int
    bad_rate_pct: float


class SamplingSummary(BaseModel):
    train: SampleGroupSummary
    test: SampleGroupSummary
    oot: SampleGroupSummary
    excluded: SampleGroupSummary


class BinningConfigIn(BaseModel):
    max_bins: int = 10
    min_bin_size: float = 0.05
    variables: list[str] | None = None


class BinRowOut(BaseModel):
    label: str
    n_total: int
    n_good: int
    n_bad: int
    bad_rate_pct: float
    pct_of_total: float
    woe: float


class VariableBinningOut(BaseModel):
    variable: str
    kind: str
    iv: float
    bins: list[BinRowOut]
    cutpoints: list[float] | None = None
    categories_map: dict[str, str] | None = None


class BinningSummaryItem(BaseModel):
    variable: str
    kind: str
    iv: float
    n_bins: int


class SelectionConfigIn(BaseModel):
    min_iv: float = 0.02
    max_corr: float = 0.7
    max_vif: float = 5.0


class DroppedVariable(BaseModel):
    variable: str
    reason: str


class SelectionResultOut(BaseModel):
    selected: list[str]
    dropped: list[DroppedVariable]
    correlation_matrix: dict[str, dict[str, float]]
    vif: dict[str, float]


class ModelingConfigIn(BaseModel):
    variables: list[str] | None = None


class CoefficientOut(BaseModel):
    variable: str
    coefficient: float
    std_error: float
    p_value: float
    z_value: float


class ModelOut(BaseModel):
    variables: list[str]
    intercept: float
    coefficients: list[CoefficientOut]
    n_obs: int
    log_likelihood: float
    pseudo_r2: float
    aic: float
    fitted_params: dict[str, float]
