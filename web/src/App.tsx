import { Route, Routes } from "react-router-dom";
import "./App.css";
import ProjectDetail from "./pages/ProjectDetail";
import ProjectList from "./pages/ProjectList";

function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectList />} />
      <Route path="/projects/:id" element={<ProjectDetail />} />
    </Routes>
  );
}

export default App;
