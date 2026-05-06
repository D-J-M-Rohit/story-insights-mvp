import { createContext, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AssessmentFlow from "./components/AssessmentFlow";
import AuthScreen from "./components/AuthScreen";
import Dashboard from "./components/Dashboard";
import ReportViewer from "./components/ReportViewer";
import { clearToken, getToken, setToken } from "./api";

export const SessionContext = createContext(null);

export default function App() {
  const [token, setTokenState] = useState(getToken());
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);

  function login(userData, authToken) {
    setToken(authToken);
    setTokenState(authToken);
    setUser(userData);
  }

  function logout() {
    clearToken();
    setTokenState("");
    setUser(null);
    setSession(null);
  }

  const value = useMemo(
    () => ({ token, user, session, setSession, login, logout }),
    [token, user, session]
  );

  const RequireAuth = ({ children }) => (token ? children : <Navigate to="/auth" replace />);

  return (
    <SessionContext.Provider value={value}>
      <BrowserRouter>
        <Routes>
          <Route path="/auth" element={token ? <Navigate to="/dashboard" replace /> : <AuthScreen />} />
          <Route path="/" element={<Navigate to={token ? "/dashboard" : "/auth"} replace />} />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/assessment"
            element={
              <RequireAuth>
                {session ? <AssessmentFlow /> : <Navigate to="/dashboard" replace />}
              </RequireAuth>
            }
          />
          <Route
            path="/report/:sessionId"
            element={
              <RequireAuth>
                <ReportViewer />
              </RequireAuth>
            }
          />
        </Routes>
      </BrowserRouter>
    </SessionContext.Provider>
  );
}
