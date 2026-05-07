import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AssessmentFlow from "./components/AssessmentFlow";
import AssessmentSessionRoute from "./components/AssessmentSessionRoute";
import AuthScreen from "./components/AuthScreen";
import ConsentScreen from "./components/ConsentScreen";
import Dashboard from "./components/Dashboard";
import ReportViewer from "./components/ReportViewer";
import { getMe, logout as logoutApi } from "./api";

export const SessionContext = createContext(null);

/** Must be a stable component identity — defining inside App remounts all children every App render (fetch storms / 429). */
function RequireAuth({ children }) {
  const ctx = useContext(SessionContext);
  const user = ctx?.user;
  return user ? children : <Navigate to="/auth" replace />;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    async function rehydrate() {
      try {
        const me = await getMe();
        setUser(me);
      } catch (_) {
        setUser(null);
      } finally {
        setAuthLoading(false);
      }
    }
    rehydrate();
  }, []);

  const login = useCallback((userData) => {
    setUser(userData);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch (_) {
      // Keep UI logout resilient even if server cookie was already cleared.
    }
    setUser(null);
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ user, session, setSession, login, logout }),
    [user, session, login, logout]
  );

  if (authLoading) return <div className="page center">Loading...</div>;

  return (
    <SessionContext.Provider value={value}>
      <BrowserRouter>
        <Routes>
          <Route path="/auth" element={user ? <Navigate to="/dashboard" replace /> : <AuthScreen />} />
          <Route path="/" element={<Navigate to={user ? "/dashboard" : "/auth"} replace />} />
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/consent"
            element={
              <RequireAuth>
                <ConsentScreen />
              </RequireAuth>
            }
          />
          <Route
            path="/assessment/:sessionId"
            element={
              <RequireAuth>
                <AssessmentSessionRoute />
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
