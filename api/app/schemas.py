from __future__ import annotations

from pydantic import BaseModel

from credittool_engine.project import ScorecardType, StepStatus


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
