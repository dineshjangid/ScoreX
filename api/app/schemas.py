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
