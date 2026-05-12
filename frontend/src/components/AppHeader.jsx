import { useContext } from "react";
import { useNavigate } from "react-router-dom";
import { LayoutDashboard, LogOut } from "lucide-react";
import { SessionContext } from "../App";
import BrandLogo from "./BrandLogo";

/**
 * @param {{ title?: string; showDashboard?: boolean; showLogout?: boolean }} props
 */
export default function AppHeader({ title, showDashboard = true, showLogout = true }) {
  const navigate = useNavigate();
  const { logout } = useContext(SessionContext);

  return (
    <header className="app-header no-print" role="banner">
      <div className="app-header-inner">
        <button
          type="button"
          className="app-header-brand"
          onClick={() => navigate("/dashboard")}
          aria-label="Psychometric Insights home, go to dashboard"
        >
          <BrandLogo size="sm" showText />
        </button>
        {title ? <span className="app-header-title">{title}</span> : <span className="app-header-title-spacer" aria-hidden />}
        <div className="app-header-actions">
          {showDashboard ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate("/dashboard")}>
              <LayoutDashboard size={18} aria-hidden />
              <span>Dashboard</span>
            </button>
          ) : null}
          {showLogout ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => logout()}>
              <LogOut size={18} aria-hidden />
              <span>Logout</span>
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
