import { useOutletContext, useParams } from "react-router-dom";
import { STEP_LABELS } from "../api";
import BinningPanel from "../components/BinningPanel";
import DataIngestionPanel from "../components/DataIngestionPanel";
import DecisionTreePanel from "../components/DecisionTreePanel";
import ModelingPanel from "../components/ModelingPanel";
import ReasonCodesPanel from "../components/ReasonCodesPanel";
import ReportingPanel from "../components/ReportingPanel";
import SamplingPanel from "../components/SamplingPanel";
import ScalingPanel from "../components/ScalingPanel";
import SelectionPanel from "../components/SelectionPanel";
import TargetDefinitionPanel from "../components/TargetDefinitionPanel";
import ValidationPanel from "../components/ValidationPanel";
import type { ProjectOutletContext } from "./ProjectLayout";

export default function StepPage() {
  const { step } = useParams<{ step: string }>();
  const { project, setProject } = useOutletContext<ProjectOutletContext>();
  const columns = project.artifacts.data_ingestion?.columns ?? [];

  function renderBody() {
    switch (step) {
      case "data_ingestion":
        return <DataIngestionPanel project={project} onUploaded={setProject} />;
      case "target_definition":
        return columns.length > 0 ? (
          <TargetDefinitionPanel project={project} columns={columns} onSaved={setProject} />
        ) : (
          <p className="muted">Upload a dataset first.</p>
        );
      case "sampling":
        return <SamplingPanel project={project} columns={columns} onSaved={setProject} />;
      case "binning":
        return <BinningPanel project={project} onSaved={setProject} />;
      case "variable_selection":
        return <SelectionPanel project={project} onSaved={setProject} />;
      case "modeling":
        return <ModelingPanel project={project} onSaved={setProject} />;
      case "scaling":
        return <ScalingPanel project={project} onSaved={setProject} />;
      case "validation":
        return <ValidationPanel project={project} onSaved={setProject} />;
      case "reason_codes":
        return <ReasonCodesPanel project={project} onSaved={setProject} />;
      case "reporting":
        return <ReportingPanel project={project} onSaved={setProject} />;
      case "decision_tree":
        return <DecisionTreePanel project={project} onSaved={setProject} />;
      default:
        return <p className="error">Unknown step "{step}"</p>;
    }
  }

  const status = project.step_status[step ?? ""] ?? "not_started";

  return (
    <div className="step-page">
      <div className="step-page-header">
        <h1>{STEP_LABELS[step ?? ""] ?? step}</h1>
        <span className={`status-pill status-${status}`}>{status.replace("_", " ")}</span>
      </div>
      <div className="card step-card">{renderBody()}</div>
    </div>
  );
}
