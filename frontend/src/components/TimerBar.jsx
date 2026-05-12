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
  const ratio = seconds > 0 ? remaining / seconds : 1;
  const fillClass =
    ratio <= 0.12 ? "timer-fill timer-fill--critical" : ratio <= 0.28 ? "timer-fill timer-fill--warn" : "timer-fill";

  return (
    <div className="timer-wrap no-print">
      <div className="timer-row">
        <span>Time remaining</span>
        <strong>
          {remaining}s <span className="muted" style={{ fontWeight: 500 }}> / {seconds}s</span>
        </strong>
      </div>
      <div className="timer-track" role="progressbar" aria-valuemin={0} aria-valuemax={seconds} aria-valuenow={remaining}>
        <div className={fillClass} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
