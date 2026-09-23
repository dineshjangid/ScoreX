"""Save/load a fitted model object (any of the ml_benchmark algorithms) to
disk, so a project's chosen final model can be reused across requests —
for validation, reason codes, batch scoring, and model-file export — without
refitting it every time.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib


def save_model(model: Any, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: str | Path) -> Any:
    return joblib.load(path)


def model_file_exists(path: str | Path | None) -> bool:
    return bool(path) and os.path.exists(path)
