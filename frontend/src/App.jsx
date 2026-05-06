import { createContext, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AssessmentFlow from "./components/AssessmentFlow";
import ConsentScreen from "./components/ConsentScreen";
import ReportViewer from "./components/ReportViewer";

export const SessionContext = createContext(null);

export default function App() {
  const [session, setSession] = useState(null);
  const value = useMemo(() => ({ session, setSession }), [session]);
  return (
    <SessionContext.Provider value={value}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ConsentScreen />} />
          <Route path="/assessment" element={session ? <AssessmentFlow /> : <Navigate to="/" replace />} />
          <Route path="/report/:sessionId" element={<ReportViewer />} />
        </Routes>
      </BrowserRouter>
    </SessionContext.Provider>
  );
}
