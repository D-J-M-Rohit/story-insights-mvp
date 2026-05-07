import { useContext, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { getSessionState } from "../api";
import { SessionContext } from "../App";
import AssessmentFlow from "./AssessmentFlow";

export default function AssessmentSessionRoute() {
  const { sessionId } = useParams();
  const { setSession } = useContext(SessionContext);
  const [latestScene, setLatestScene] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();

  // Hydrate once per route param. Do not depend on navigate/setSession — unstable identities
  // can retrigger this effect hundreds of times per second (429 + unusable UI).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await getSessionState(sessionId);
        if (cancelled) return;
        if (st.session.status !== "active") {
          navigate(`/report/${sessionId}`, { replace: true });
          return;
        }
        setSession({
          id: st.session.id,
          user_id: st.session.user_id,
          scenario: st.session.scenario,
          max_turns: st.session.max_turns,
          status: st.session.status,
          scenario_pack_id: st.session.scenario_pack_id,
          policy_version: st.session.policy_version,
          created_at: st.session.created_at,
        });
        setLatestScene(st.latest_scene);
      } catch (_) {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional single fetch per sessionId
  }, [sessionId]);

  if (loading) return <div className="page center">Loading assessment...</div>;
  if (failed) return <Navigate to="/dashboard" replace />;
  return <AssessmentFlow initialScene={latestScene} />;
}
