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
    observation_date_column: str | None = None
    performance_window_months: int | None = None


class TargetSummary(BaseModel):
    n_total: int
    n_good: int
    n_bad: int
    n_excluded: int
    bad_rate_pct: float


class VintageRow(BaseModel):
    cohort: str
    n_total: int
    n_bad: int
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


class ScalingConfigIn(BaseModel):
    pdo: float = 20.0
    base_score: float = 600.0
    base_odds: float = 50.0


class BinPointsOut(BaseModel):
    label: str
    woe: float
    points: int


class VariablePointsOut(BaseModel):
    variable: str
    coefficient: float
    bins: list[BinPointsOut]


class ScoreDistribution(BaseModel):
    mean: float
    std: float
    min: float
    p25: float
    median: float
    p75: float
    max: float


class ScorecardOut(BaseModel):
    factor: float
    offset: float
    base_points: int
    variables: list[VariablePointsOut]
    min_score: int
    max_score: int
    train_score_distribution: ScoreDistribution


class SampleMetrics(BaseModel):
    n_total: int
    n_bad: int
    bad_rate_pct: float
    ks: float
    auc: float
    gini: float


class StabilityBucket(BaseModel):
    bucket: str
    reference_pct: float
    comparison_pct: float
    contribution: float


class StabilityResult(BaseModel):
    index: float
    buckets: list[StabilityBucket]


class DecileRow(BaseModel):
    score_range: str
    n_total: int
    n_bad: int
    bad_rate_pct: float
    pct_of_total_bad: float


class RocPoint(BaseModel):
    fpr: float
    tpr: float


class MLBenchmarkConfigIn(BaseModel):
    variables: list[str] | None = None
    n_estimators: int = 100
    max_depth: int = 3


class FeatureImportanceOut(BaseModel):
    variable: str
    mean_abs_shap: float


class MLBenchmarkOut(BaseModel):
    variables: list[str]
    train_auc: float
    test_auc: float
    train_gini: float
    test_gini: float
    feature_importance: list[FeatureImportanceOut]


class ReasonCodesConfigIn(BaseModel):
    top_n: int = 3
    preview_rows: int = 20


class ReasonCodesOut(BaseModel):
    top_n: int
    n_scored: int
    preview: list[dict]


class ValidationOut(BaseModel):
    train: SampleMetrics
    test: SampleMetrics
    oot: SampleMetrics | None
    roc_train: list[RocPoint]
    decile_table_train: list[DecileRow]
    psi_test_vs_train: StabilityResult
    psi_oot_vs_train: StabilityResult | None
    csi_test_vs_train: dict[str, StabilityResult]
    csi_oot_vs_train: dict[str, StabilityResult] | None
