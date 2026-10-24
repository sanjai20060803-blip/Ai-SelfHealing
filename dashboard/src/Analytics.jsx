import { useEffect, useState } from "react";
import api from "./api";
import { StackBar, round1 } from "./ui";

// For each reading: is a lower number better?
const ROWS = [
  { name: "Latency", unit: "ms", before: "latencyBefore", after: "latencyAfter", lowerIsBetter: true },
  { name: "Packet loss", unit: "%", before: "lossBefore", after: "lossAfter", lowerIsBetter: true },
  { name: "Bandwidth", unit: "Mbps", before: "bandwidthBefore", after: "bandwidthAfter", lowerIsBetter: false },
];

function change(before, after) {
  if (!before) return null;
  return ((after - before) / before) * 100;
}

function Compare({ row, avg }) {
  const b = avg[row.before] ?? 0;
  const a = avg[row.after] ?? 0;
  const max = Math.max(b, a, 0.0001);
  const pct = change(b, a);
  const better = pct === null ? null : row.lowerIsBetter ? pct < 0 : pct > 0;
  const sign = pct === null ? "" : pct > 0 ? "+" : "−";
  const tone = better === null ? "neutral" : better ? "good" : "bad";

  return (
    <div>
      <div className="compare-row-head">
        <strong>{row.name}</strong>
        {pct !== null && (
          <span className={"chip tone-" + tone}>
            {sign}
            {Math.abs(Math.round(pct)).toLocaleString()}%{better ? " better" : " worse"}
          </span>
        )}
      </div>
      <div className="compare-bar">
        <span>Before</span>
        <div className="track">
          <i style={{ width: (b / max) * 100 + "%", background: "#b7c1d1" }} />
        </div>
        <span className="num">
          {round1(b)} {row.unit}
        </span>
      </div>
      <div className="compare-bar">
        <span>After</span>
        <div className="track">
          <i style={{ width: (a / max) * 100 + "%", background: "var(--brand)" }} />
        </div>
        <span className="num">
          {round1(a)} {row.unit}
        </span>
      </div>
    </div>
  );
}

export default function Analytics() {
  const [s, setS] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await api.get("/analytics/summary");
        if (alive) setS(res.data);
      } catch {
        /* keep the last values */
      }
    };
    load();
    const timer = setInterval(load, 6000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (!s) return null;

  const pc = s.predictionCounts || {};
  const rec = s.recoveries || {};
  const mail = s.emails || {};
  const total = (pc.Normal || 0) + (pc.Abnormal || 0) + (pc.Failure || 0);
  const pct = (n) => (total ? Math.round((n / total) * 100) + "%" : "0%");

  return (
    <section className="panel results" aria-label="Results so far">
      <div>
        <div className="panel-head">
          <h2 className="panel-title">Results so far</h2>
        </div>

        <dl className="facts">
          <div className="fact">
            <dt>Readings checked</dt>
            <dd>{(s.totalMetrics ?? 0).toLocaleString()}</dd>
          </div>
          <div className="fact">
            <dt>Recoveries run</dt>
            <dd>
              {rec.total ?? 0}
              <small>
                {rec.healed ?? 0} healed, {rec.partial ?? 0} partly, {rec.failed ?? 0} failed
              </small>
            </dd>
          </div>
          <div className="fact">
            <dt>Success rate</dt>
            <dd>{round1(rec.successRatePct)}%</dd>
          </div>
          <div className="fact">
            <dt>Emails sent</dt>
            <dd>
              {mail.sent ?? 0}
              <small>{mail.failed ?? 0} failed</small>
            </dd>
          </div>
        </dl>

        <div style={{ marginTop: 18 }}>
          <div className="control-label" style={{ marginBottom: 8 }}>
            What the AI saw across all readings
          </div>
          <StackBar
            parts={[
              { label: "Normal", value: pc.Normal || 0, color: "var(--good-fill)", text: pct(pc.Normal || 0) },
              { label: "Abnormal", value: pc.Abnormal || 0, color: "var(--warn-fill)", text: pct(pc.Abnormal || 0) },
              { label: "Failure", value: pc.Failure || 0, color: "var(--bad-fill)", text: pct(pc.Failure || 0) },
            ]}
          />
        </div>
      </div>

      <div>
        <div className="panel-head">
          <h2 className="panel-title">Average before and after recovery</h2>
        </div>
        {rec.total ? (
          <div className="compare">
            {ROWS.map((r) => (
              <Compare key={r.name} row={r} avg={s.averageBeforeAfter || {}} />
            ))}
          </div>
        ) : (
          <p className="muted">
            No recoveries yet. Choose Failure as the test scenario, then press Run self-healing now
            to see the before and after numbers.
          </p>
        )}
      </div>
    </section>
  );
}