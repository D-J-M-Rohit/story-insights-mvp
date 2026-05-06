import { useEffect, useRef, useState } from "react";

export default function TimerBar({ seconds, onExpire, sceneId }) {
  const [remaining, setRemaining] = useState(seconds);
  const expiredRef = useRef(false);

  useEffect(() => {
    setRemaining(seconds);
    expiredRef.current = false;
  }, [seconds, sceneId]);

  useEffect(() => {
    const tick = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(tick);
          if (!expiredRef.current) {
            expiredRef.current = true;
            onExpire?.();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [onExpire, sceneId]);

  const pct = seconds > 0 ? (remaining / seconds) * 100 : 0;
  return (
    <div className="timer-wrap">
      <div className="timer-row">
        <span>Time left</span>
        <strong>{remaining}s</strong>
      </div>
      <div className="timer-track">
        <div className="timer-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
