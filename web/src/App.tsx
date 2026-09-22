import { Route, Routes } from "react-router-dom";
import "./App.css";
import AuditTrailPage from "./pages/AuditTrailPage";
import BatchScoringPage from "./pages/BatchScoringPage";
import Overview from "./pages/Overview";
import ProjectLayout from "./pages/ProjectLayout";
import ProjectList from "./pages/ProjectList";
import StepPage from "./pages/StepPage";
import VersionsPage from "./pages/VersionsPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectList />} />
      <Route path="/projects/:id" element={<ProjectLayout />}>
        <Route index element={<Overview />} />
        <Route path="batch-scoring" element={<BatchScoringPage />} />
        <Route path="versions" element={<VersionsPage />} />
        <Route path="audit-trail" element={<AuditTrailPage />} />
        <Route path=":step" element={<StepPage />} />
      </Route>
    </Routes>
  );
}

export default App;
