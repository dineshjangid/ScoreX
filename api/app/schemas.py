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


class ManualBinningIn(BaseModel):
    cutpoints: list[float] | None = None
    categories_map: dict[str, str] | None = None


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


class HistogramBin(BaseModel):
    bin_start: float
    bin_end: float
    count: int


class MLBenchmarkConfigIn(BaseModel):
    variables: list[str] | None = None
    n_estimators: int = 100
    max_depth: int = 3
    algorithm: str = "xgboost"  # "xgboost" | "random_forest" | "lightgbm" | "catboost" | "all"


class FeatureImportanceOut(BaseModel):
    variable: str
    mean_abs_shap: float


class MLBenchmarkOut(BaseModel):
    algorithm: str
    variables: list[str]
    train_auc: float
    test_auc: float
    train_gini: float
    test_gini: float
    feature_importance: list[FeatureImportanceOut]


class MLBenchmarkAllOut(BaseModel):
    results: dict[str, MLBenchmarkOut]


class ReasonCodesConfigIn(BaseModel):
    top_n: int = 3
    preview_rows: int = 20


class ReasonCodesOut(BaseModel):
    top_n: int
    n_scored: int
    preview: list[dict]


class BatchScoringOut(BaseModel):
    filename: str
    n_scored: int
    top_n: int
    score_distribution: ScoreDistribution
    preview: list[dict]


class ValidationOut(BaseModel):
    train: SampleMetrics
    test: SampleMetrics
    oot: SampleMetrics | None
    roc_train: list[RocPoint]
    decile_table_train: list[DecileRow]
    score_histogram_train: list[HistogramBin]
    psi_test_vs_train: StabilityResult
    psi_oot_vs_train: StabilityResult | None
    csi_test_vs_train: dict[str, StabilityResult]
    csi_oot_vs_train: dict[str, StabilityResult] | None


class VersionCreateIn(BaseModel):
    label: str | None = None


class VersionSummary(BaseModel):
    id: str
    version_number: int
    label: str | None
    is_champion: bool
    created_at: str
    n_variables: int
    train_auc: float | None
    train_ks: float | None
    train_gini: float | None
    score_range: str | None


class VersionDetail(VersionSummary):
    snapshot: dict


class DecisionTreeConfigIn(BaseModel):
    variables: list[str] | None = None
    max_depth: int = 4
    min_leaf_size_frac: float = 0.05
    criterion: str = "gini"


class BranchRuleOut(BaseModel):
    variable: str
    kind: str
    operator: str
    threshold: float | None = None
    values: list[str] | None = None


class TreeNodeOut(BaseModel):
    id: str
    parent_id: str | None
    depth: int
    branch_rule: BranchRuleOut | None
    branch_description: str
    n_total: int
    n_bad: int
    n_good: int
    bad_rate_pct: float
    is_leaf: bool
    split_variable: str | None
    split_kind: str | None
    split_threshold: float | None
    split_left_values: list[str] | None
    split_right_values: list[str] | None
    children: list[str]
    policy: str | None


class DecisionTreeOut(BaseModel):
    root_id: str
    nodes: dict[str, TreeNodeOut]


class NodeSplitIn(BaseModel):
    variable: str
    kind: str
    threshold: float | None = None
    left_values: list[str] | None = None
    right_values: list[str] | None = None


class NodePolicyIn(BaseModel):
    policy: str | None = None


class LeafRuleOut(BaseModel):
    node_id: str
    rule: str
    n_total: int
    n_bad: int
    bad_rate_pct: float
    policy: str | None


class AuditLogOut(BaseModel):
    id: str
    username: str
    role: str
    action: str
    detail: str | None
    created_at: str
