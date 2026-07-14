import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Setup } from "./pages/Setup";
import { Providers } from "./pages/Providers";
import { MeetingPrep } from "./pages/MeetingPrep";
import { LiveMeeting } from "./pages/LiveMeeting";
import { History, HistoryDetail } from "./pages/History";
import { Diagnostics } from "./pages/Diagnostics";
import { Settings } from "./pages/Settings";
import { CodexAuth } from "./pages/CodexAuth";
import { ProjectDashboard, Projects } from "./pages/Projects";
import { Actions, Decisions, Knowledge } from "./pages/KnowledgeWork";
import { AuthGate } from "./components/AuthGate";
import { Access } from "./pages/Access";

export function App() { return <Routes><Route element={<AuthGate><Layout/></AuthGate>}>
  <Route index element={localStorage.getItem("meeting-copilot-setup") ? <Dashboard/> : <Navigate to="/setup" replace/>}/>
  <Route path="setup" element={<Setup/>}/><Route path="providers" element={<Providers/>}/>
  <Route path="codex" element={<CodexAuth/>}/>
  <Route path="projects" element={<Projects/>}/><Route path="projects/:id" element={<ProjectDashboard/>}/>
  <Route path="decisions" element={<Decisions/>}/><Route path="actions" element={<Actions/>}/><Route path="knowledge" element={<Knowledge/>}/>
  <Route path="meetings" element={<MeetingPrep/>}/><Route path="meetings/new" element={<MeetingPrep/>}/><Route path="meetings/:id" element={<LiveMeeting/>}/>
  <Route path="history" element={<History/>}/><Route path="history/:id" element={<HistoryDetail/>}/>
  <Route path="diagnostics" element={<Diagnostics/>}/><Route path="settings" element={<Settings/>}/>
  <Route path="access" element={<Access/>}/>
</Route></Routes>; }
