import { Route, Routes } from "react-router-dom";
import "./App.css";
import BatchScoringPage from "./pages/BatchScoringPage";
import Overview from "./pages/Overview";
import ProjectLayout from "./pages/ProjectLayout";
import ProjectList from "./pages/ProjectList";
import StepPage from "./pages/StepPage";

function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectList />} />
      <Route path="/projects/:id" element={<ProjectLayout />}>
        <Route index element={<Overview />} />
        <Route path="batch-scoring" element={<BatchScoringPage />} />
        <Route path=":step" element={<StepPage />} />
      </Route>
    </Routes>
  );
}

export default App;
