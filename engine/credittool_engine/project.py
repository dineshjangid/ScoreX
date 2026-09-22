"""Core domain object: a single scorecard-build-in-progress.

A Project tracks one scorecard development lifecycle (data -> target ->
sampling -> binning -> modeling -> scaling -> validation -> reporting).
It holds no I/O or web concerns — the API layer is responsible for
persisting/loading Project instances (see api/app/models.py).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ScorecardType(str, Enum):
    APPLICATION = "application"
    BEHAVIOURAL = "behavioural"


class StepName(str, Enum):
    DATA_INGESTION = "data_ingestion"
    TARGET_DEFINITION = "target_definition"
    SAMPLING = "sampling"
    BINNING = "binning"
    VARIABLE_SELECTION = "variable_selection"
    MODELING = "modeling"
    SCALING = "scaling"
    VALIDATION = "validation"
    REASON_CODES = "reason_codes"
    REPORTING = "reporting"


class StepStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


# The fixed lifecycle order every project moves through. UIs use this to
# render the wizard's step list; engine subpackages implement each step.
STEP_ORDER: list[StepName] = [
    StepName.DATA_INGESTION,
    StepName.TARGET_DEFINITION,
    StepName.SAMPLING,
    StepName.BINNING,
    StepName.VARIABLE_SELECTION,
    StepName.MODELING,
    StepName.SCALING,
    StepName.VALIDATION,
    StepName.REASON_CODES,
    StepName.REPORTING,
]


@dataclass
class Project:
    name: str
    scorecard_type: ScorecardType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    step_status: dict[StepName, StepStatus] = field(
        default_factory=lambda: {step: StepStatus.NOT_STARTED for step in STEP_ORDER}
    )
    # Free-form per-step results (profiling summary, binning tables, model
    # coefficients, validation metrics, ...). Keyed by StepName.value.
    # Concrete shapes are defined by each engine subpackage as it's built.
    artifacts: dict[str, Any] = field(default_factory=dict)

    def mark_step(self, step: StepName, status: StepStatus) -> None:
        self.step_status[step] = status
        self.updated_at = datetime.now(timezone.utc)

    def set_artifact(self, step: StepName, payload: Any) -> None:
        self.artifacts[step.value] = payload
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scorecard_type": self.scorecard_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "step_status": {step.value: status.value for step, status in self.step_status.items()},
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        project = cls(
            name=data["name"],
            scorecard_type=ScorecardType(data["scorecard_type"]),
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        project.step_status = {
            StepName(k): StepStatus(v) for k, v in data.get("step_status", {}).items()
        }
        project.artifacts = data.get("artifacts", {})
        return project
