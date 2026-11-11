import { useEffect, useState } from "react";
import { clockUTC } from "../time";

interface Props {
  pending: number;
  high: number;
  online: boolean;
  mock: boolean;
  operator: string;
}

function Metric({ label, value, tone, mono }: { label: string; value: string; tone?: string; mono?: boolean }) {
  return (
    <div className={`metric ${tone ? `metric--${tone}` : ""}`}>
      <span className="metric-label">{label}</span>
      <span className={`metric-value ${mono ? "mono" : ""}`}>{value}</span>
    </div>
  );
}

export function StatusBar({ pending, high, online, mock, operator }: Props) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="statusbar">
      <div className="brand">
        <span className="brand-pulse" />
        <span className="brand-mark">AIC</span>
        <span className="brand-sub">INCIDENT COMMANDER</span>
      </div>
      <div className="telemetry">
        <Metric label="PENDING" value={String(pending).padStart(2, "0")} />
        <Metric label="HIGH RISK" value={String(high).padStart(2, "0")} tone={high > 0 ? "alert" : undefined} />
        <Metric label="UTC" value={clockUTC(now)} mono />
        <div className={`conn ${online ? "conn--up" : "conn--down"}`}>
          <span className="conn-dot" />
          {mock ? "DEMO FEED" : online ? "API ONLINE" : "API OFFLINE"}
        </div>
        <div className="operator" title="active operator">
          {operator}
        </div>
      </div>
    </header>
  );
}
