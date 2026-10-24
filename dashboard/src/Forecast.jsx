import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import api from "./api";
import { ChartTip, Chip, STATUS, time } from "./ui";

const WARN_AT = 35; // Must match WARNING_RISK in network/services/monitor.py
const CAUTION_AT = 20;

const TREND = {
  worsening: "getting worse",
  improving: "getting better",
  stable: "steady",
};

export default function Forecast({ current }) {
  const [list, setList] = useState([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await api.get("/forecast");
        if (alive) setList(res.data);
      } catch {
        /* backend offline: keep the last values */
      }
    };
    load();
    const timer = setInterval(load, 4000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const latest = list.length ? list[0] : null;

  if (!latest) {
    return (
      <section className="panel forecast">
        <h2 className="panel-title">Forecast</h2>
        <p className="muted">
          The forecast needs 6 readings, about one minute after the backend starts. Nothing to do
          until then.
        </p>
      </section>
    );
  }

  const data = [...list].reverse().map((f) => ({ full: time(f.createdAt), risk: f.riskScore }));
  const risk = latest.riskScore;
  // The early warning is only useful while the network still looks healthy right now.
  const warning = risk >= WARN_AT && current === "Normal";
  const tone = warning ? "warn" : STATUS[latest.forecastStatus]?.tone || "neutral";
  const trend = TREND[latest.trend] || TREND.stable;

  const sentence = warning
    ? `Trouble is likely within about ${latest.horizonSeconds} seconds.`
    : latest.forecastStatus === "Normal"
      ? `Expected to stay healthy over the next ${latest.horizonSeconds} seconds.`
      : latest.forecastStatus === "Failure"
        ? `Expected to fail within about ${latest.horizonSeconds} seconds.`
        : `Expected to become unstable within about ${latest.horizonSeconds} seconds.`;

  return (
    <section className="panel forecast" aria-label="Forecast">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2 className="panel-title">Forecast</h2>
        <Chip tone={tone}>{warning ? "At risk" : latest.forecastStatus}</Chip>
      </div>

      {warning && (
        <div className="notice tone-bad" role="alert">
          <span>
            <b>Early warning.</b> The connection still looks fine, but trouble is likely soon. Save
            your work and be ready to reconnect.
          </span>
        </div>
      )}

      <p className="forecast-sentence">{sentence}</p>

      <div className="meter-wrap">
        <div className="meter" role="img" aria-label={`Risk ${risk} out of 100`}>
          <i style={{ width: CAUTION_AT + "%", background: "var(--good-bg)" }} />
          <i style={{ width: WARN_AT - CAUTION_AT + "%", background: "var(--warn-bg)" }} />
          <i style={{ width: 100 - WARN_AT + "%", background: "var(--bad-bg)" }} />
        </div>
        <span className="meter-marker" style={{ left: Math.min(100, risk) + "%", top: -3 }} />
        <div className="meter-scale" aria-hidden="true">
          <span style={{ left: 0 }}>0</span>
          <span style={{ left: WARN_AT + "%" }}>Warning at {WARN_AT}</span>
          <span style={{ left: "100%" }}>100</span>
        </div>
      </div>

      <div className="facts-inline">
        <span>
          Risk <b>{risk} of 100</b>
        </span>
        <span>
          Trend <b>{trend}</b>
        </span>
        <span>
          AI is <b>{Math.round(latest.confidence * 100)}%</b> sure
        </span>
      </div>

      <p className="small muted" style={{ marginBottom: -8 }}>
        Risk over the last readings. The dashed line is the warning level.
      </p>
      <div style={{ height: 92 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 6, left: 6, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#edf0f5" />
            <XAxis dataKey="full" hide />
            <YAxis domain={[0, 100]} hide />
            <Tooltip
              content={<ChartTip />}
              cursor={{ stroke: "#9aa6ba", strokeDasharray: "3 3" }}
            />
            <ReferenceLine y={WARN_AT} stroke="#e5484d" strokeDasharray="4 4" />
            <Line
              type="monotone"
              dataKey="risk"
              name="Risk"
              stroke="var(--s-latency)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}