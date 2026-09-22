from credittool_engine.project import Project, ScorecardType, StepName, StepStatus


def test_new_project_has_all_steps_not_started():
    project = Project(name="Test", scorecard_type=ScorecardType.APPLICATION)
    assert all(status == StepStatus.NOT_STARTED for status in project.step_status.values())


def test_mark_step_updates_status():
    project = Project(name="Test", scorecard_type=ScorecardType.APPLICATION)
    project.mark_step(StepName.DATA_INGESTION, StepStatus.COMPLETE)
    assert project.step_status[StepName.DATA_INGESTION] == StepStatus.COMPLETE


def test_round_trip_dict_serialization():
    project = Project(name="Roundtrip", scorecard_type=ScorecardType.BEHAVIOURAL)
    project.mark_step(StepName.DATA_INGESTION, StepStatus.COMPLETE)
    project.set_artifact(StepName.DATA_INGESTION, {"rows": 100})

    restored = Project.from_dict(project.to_dict())

    assert restored.id == project.id
    assert restored.scorecard_type == ScorecardType.BEHAVIOURAL
    assert restored.step_status[StepName.DATA_INGESTION] == StepStatus.COMPLETE
    assert restored.artifacts["data_ingestion"] == {"rows": 100}


def test_set_extra_stores_side_artifact_without_touching_step_status():
    project = Project(name="Test", scorecard_type=ScorecardType.APPLICATION)
    project.set_extra("ml_benchmark", {"train_auc": 0.8})

    assert project.artifacts["ml_benchmark"] == {"train_auc": 0.8}
    assert all(status == StepStatus.NOT_STARTED for status in project.step_status.values())
