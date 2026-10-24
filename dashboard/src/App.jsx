import { useCallback, useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import api from "./api";
import Analytics from "./Analytics";
import Forecast from "./Forecast";
import Meeting from "./Meeting";
import Report, { downloadCsv } from "./Report";
import Why from "./Why";
import {
  ChartTip,
  Chip,
  MAIL,
  MAIL_TYPE,
  STATUS,
  Spark,
  StackBar,
  VERDICT,
  pretty,
  prettyList,
  round1,
  time,
} from "./ui";

const MODES = [
  { value: "SIMULATION", label: "Simulation" },
  { value: "REAL", label: "Real network" },
];
const SCENARIOS = ["NORMAL", "ABNORMAL", "FAILURE", "DEGRADING", "RANDOM"];

// What the "limit" for each reading is, taken from the diagnosis rules in the backend.
const VITALS = [
  { key: "latencyMs", label: "Latency", unit: "ms", note: "Limit 100 ms", over: (v) => v > 100, tone: "bad", color: "var(--s-latency)" },
  { key: "packetLossPct", label: "Packet loss", unit: "%", note: "Limit 5%", over: (v) => v > 5, tone: "bad", color: "var(--s-loss)" },
  { key: "jitterMs", label: "Jitter", unit: "ms", note: "Limit 20 ms", over: (v) => v > 20, tone: "bad", color: "var(--s-jitter)" },
  { key: "bandwidthMbps", label: "Bandwidth", unit: "Mbps", note: "Needs 5 Mbps", over: (v) => v < 5, tone: "bad", color: "var(--s-bandwidth)" },
  { key: "cpuPct", label: "CPU", unit: "%", note: "Limit 85%", over: (v) => v > 85, tone: "warn", color: "var(--ink-3)" },
  { key: "memoryPct", label: "Memory", unit: "%", note: "Limit 90%", over: (v) => v > 90, tone: "warn", color: "var(--ink-3)" },
  { key: "signalStrength", label: "Signal", unit: "%", note: "Low below 40%", over: (v) => v < 40, tone: "warn", color: "var(--ink-3)" },
];

const HEADLINE = {
  Normal: {
    title: "Connection is healthy",
    lede: (c) =>
      `The AI is ${c}% sure the network is working normally. Online classes can run without trouble.`,
  },
  Abnormal: {
    title: "Connection is unstable",
    lede: () => "Video and audio may stutter. Self-healing can bring the network back to normal.",
  },
  Failure: {
    title: "Connection is failing",
    lede: () => "Classes would drop out right now. Run self-healing to restore the connection.",
  },
};

const shortClock = (s) => String(s).replace(/:\d{2}(?= |$)/, "");

const axisTick = { fontSize: 12, fill: "#5d6a82" };

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="9" stroke="#fff" strokeOpacity="0.35" strokeWidth="1.6" />
      <path
        d="M3.5 11.5h4l2-4.5 3 8 2-3.5h4"
        stroke="#fff"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function MetricChart({ title, data, lines, unit }) {
  return (
    <div className="chart">
      <div className="panel-head" style={{ marginBottom: 0 }}>
        <h2 className="panel-title">{title}</h2>
        {lines.length > 1 && (
          <div className="chart-legend">
            {lines.map((l) => (
              <span key={l.key}>
                <i className="swatch" style={{ background: l.color }} />
                {l.name}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#edf0f5" />
            <XAxis
              dataKey="full"
              tickFormatter={shortClock}
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: "#e1e6ee" }}
              interval="preserveStartEnd"
              minTickGap={64}
            />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} width={46} />
            <Tooltip
              content={<ChartTip unit={unit} />}
              cursor={{ stroke: "#9aa6ba", strokeDasharray: "3 3" }}
            />
            {lines.map((l) => (
              <Line
                key={l.key}
                type="monotone"
                dataKey={l.key}
                name={l.name}
                stroke={l.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function App() {
  const [online, setOnline] = useState(false);
  const [status, setStatus] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [history, setHistory] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [healing, setHealing] = useState(false);
  const [emailTestPending, setEmailTestPending] = useState(false);
  const [emailTestResult, setEmailTestResult] = useState("");
  const [lastResult, setLastResult] = useState(null);
  const [hover, setHover] = useState(null);
  const [report, setReport] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [st, mt, pr, hi, no] = await Promise.all([
        api.get("/monitor/status"),
        api.get("/metrics/recent"),
        api.get("/predictions"),
        api.get("/healing/history"),
        api.get("/notifications"),
      ]);
      setStatus(st.data);
      setMetrics([...mt.data].reverse());
      setPredictions(pr.data);
      setHistory(hi.data);
      setNotifications(no.data);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function act(fn) {
    try {
      await fn();
    } catch (e) {
      console.error(e);
    } finally {
      refresh();
    }
  }

  const setMode = (m) => act(() => api.post(`/monitor/mode/${m}`));
  const setScenario = (s) => act(() => api.post(`/monitor/scenario/${s}`));
  const toggleAuto = () => act(() => api.post(`/healing/auto/${!status?.autoHeal}`));

  async function sendEmailTest() {
    setEmailTestPending(true);
    setEmailTestResult("");
    try {
      const { data } = await api.post("/notifications/test");
      setEmailTestResult(
        data.status === "SENT"
          ? "Test email sent. Check the receiving inbox and spam folder."
          : `Test email ${String(data.status).toLowerCase()}: ${data.error || "Unknown error."}`,
      );
    } catch (error) {
      const detail = error.response?.data?.detail;
      setEmailTestResult(
        typeof detail === "string" ? detail : error.message || "Could not send test email.",
      );
    } finally {
      setEmailTestPending(false);
      refresh();
    }
  }

  async function runHeal() {
    setHealing(true);
    try {
      const res = await api.post("/healing/run", null, { timeout: 60000 });
      setLastResult(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setHealing(false);
      refresh();
    }
  }

  const latest = metrics.length ? metrics[metrics.length - 1] : null;
  const pred = predictions.length ? predictions[0] : null;
  const isReal = status?.mode === "REAL";

  const chartData = metrics.map((m) => ({
    full: time(m.timestamp),
    latency: m.latencyMs,
    jitter: m.jitterMs,
    bandwidth: m.bandwidthMbps,
    loss: m.packetLossPct,
  }));

  const strip = [...predictions].slice(0, 20).reverse();
  const shown = hover !== null ? strip[hover] : null;

  const head = HEADLINE[pred?.status];
  const tone = STATUS[pred?.status]?.tone || "neutral";

  return (
    <div>
      <header className="topbar">
        <div className="topbar-in">
          <div className="brand">
            <div className="brand-mark">
              <Logo />
            </div>
            <div>
              <div className="brand-name">SELF HEAL</div>
              <div className="brand-sub">Live connection health for online classes</div>
            </div>
          </div>

          <div className="topbar-tools">
            <span className={"link-state " + (online ? "tone-good" : "tone-bad")}>
              <i className="dot" />
              {online ? "Backend online" : "Backend offline"}
            </span>
            <div className="seg" role="group" aria-label="Data source">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  aria-pressed={status?.mode === m.value}
                  onClick={() => setMode(m.value)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="page">
        {!online && (
          <div className="notice tone-bad" role="alert">
            <span>
              <b>Can't reach the backend.</b> Start the Python backend service on port 8080. This page
              reconnects by itself.
            </span>
          </div>
        )}

        <section className="hero" aria-label="Network now and forecast">
          <div className="panel now">
            <div className="now-top">
              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                {pred ? <Chip tone={tone}>{pred.status}</Chip> : <Chip>Waiting</Chip>}
                <span className="small muted">
                  {latest
                    ? "Updated " +
                      time(latest.timestamp) +
                      (isReal ? ", measured on this computer" : ", simulated data")
                    : "No reading yet"}
                </span>
              </div>
              <h1 className="headline">{head ? head.title : "Waiting for data"}</h1>
              <p className="lede">
                {head
                  ? head.lede(Math.round((pred?.confidence ?? 0) * 100))
                  : "The first reading arrives within 10 seconds of the backend starting."}
              </p>
            </div>

            {pred && (
              <StackBar
                parts={[
                  { label: "Normal", value: pred.probNormal, color: "var(--good-fill)", text: Math.round(pred.probNormal * 100) + "%" },
                  { label: "Abnormal", value: pred.probAbnormal, color: "var(--warn-fill)", text: Math.round(pred.probAbnormal * 100) + "%" },
                  { label: "Failure", value: pred.probFailure, color: "var(--bad-fill)", text: Math.round(pred.probFailure * 100) + "%" },
                ]}
              />
            )}

            <Why />

            <div className="strip-block" hidden={strip.length === 0}>
              <div className="strip" role="list" aria-label="AI result for the last 20 readings">
                {strip.map((p, i) => (
                  <button
                    key={p.id}
                    role="listitem"
                    className={"tone-" + (STATUS[p.status]?.tone || "neutral")}
                    aria-label={`${time(p.createdAt)}: ${p.status}`}
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                  />
                ))}
              </div>
              <div className="strip-foot">
                {shown ? (
                  <span>
                    <strong>{time(shown.createdAt)}</strong> {shown.status}, {Math.round(shown.confidence * 100)}% sure
                  </span>
                ) : (
                  <>
                    <span>Last {strip.length || 20} AI readings, oldest first</span>
                    <span>Latest</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <Forecast current={pred?.status} />
        </section>

        <section className="panel controls" aria-label="Controls">
          <div className="control">
            <span className="control-label" id="scn">
              Test scenario {isReal ? "(simulation only)" : ""}
            </span>
            <div className="seg" role="group" aria-labelledby="scn">
              {SCENARIOS.map((s) => (
                <button
                  key={s}
                  disabled={isReal}
                  aria-pressed={status?.scenario === s}
                  onClick={() => setScenario(s)}
                >
                  {pretty(s)}
                </button>
              ))}
            </div>
          </div>

          <div className="control">
            <span className="control-label">Automatic repair</span>
            <button
              className="switch"
              role="switch"
              aria-checked={!!status?.autoHeal}
              onClick={toggleAuto}
            >
              <span className="switch-track" />
              {status?.autoHeal ? "On, fixes problems by itself" : "Off, repair only on request"}
            </button>
          </div>

          <button className="btn-primary" onClick={runHeal} disabled={healing || !online}>
            {healing ? "Healing, please wait…" : "Run self-healing now"}
          </button>

          {lastResult && (
            <div className="result">
              <span className="muted">Last run</span>
              <Chip tone={VERDICT[lastResult.verdict]?.tone}>
                {VERDICT[lastResult.verdict]?.label || lastResult.verdict}
              </Chip>
              {lastResult.verdict === "NOT_NEEDED" ? (
                <span>{lastResult.advice || "The network is healthy, so no recovery was needed."}</span>
              ) : (
                <span>
                  {lastResult.beforeStatus} to {lastResult.afterStatus}. Problems found:{" "}
                  {prettyList(lastResult.faults)}.
                </span>
              )}
            </div>
          )}
        </section>

        <Meeting />

        <section className="panel vitals" aria-label="Current readings">
          {VITALS.map((v) => {
            const value = latest ? latest[v.key] : null;
            const over = value !== null && value !== undefined && v.over(value);
            return (
              <div className={"vital " + (over ? "tone-" + v.tone : "")} key={v.key}>
                <div className="vital-label">
                  <span className="vital-name">
                    {over && <i className="dot" role="img" aria-label="Over the limit" />}
                    {v.label}
                  </span>
                  <Spark values={metrics.map((m) => m[v.key])} color={v.color} />
                </div>
                <div className="vital-value" style={over ? { color: "var(--tone)" } : undefined}>
                  {round1(value)}
                  <small>{v.unit}</small>
                </div>
                <div
                  className="vital-foot"
                  style={over ? { color: "var(--tone)", fontWeight: 600 } : undefined}
                >
                  {over ? "Over the limit" : v.note}
                </div>
              </div>
            );
          })}
        </section>

        <section className="panel charts" aria-label="Recent readings">
          <MetricChart
            title="Latency and jitter"
            unit=" ms"
            data={chartData}
            lines={[
              { key: "latency", name: "Latency", color: "var(--s-latency)" },
              { key: "jitter", name: "Jitter", color: "var(--s-jitter)" },
            ]}
          />
          <MetricChart
            title="Bandwidth"
            unit=" Mbps"
            data={chartData}
            lines={[{ key: "bandwidth", name: "Bandwidth", color: "var(--s-bandwidth)" }]}
          />
          <MetricChart
            title="Packet loss"
            unit="%"
            data={chartData}
            lines={[{ key: "loss", name: "Packet loss", color: "var(--s-loss)" }]}
          />
        </section>

        <Analytics />

        <div className="tables">
          <section className="panel panel-pad">
            <div className="panel-head">
              <h2 className="panel-title">Recovery history</h2>
              <button
                className="btn-quiet"
                style={{ padding: "5px 12px", fontSize: 13 }}
                disabled={history.length === 0}
                onClick={() => downloadCsv(history)}
              >
                Download CSV
              </button>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Started by</th>
                    <th>Problems found</th>
                    <th>Network</th>
                    <th>Outcome</th>
                    <th>Report</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((r) => (
                    <tr key={r.id}>
                      <td className="time">{time(r.createdAt)}</td>
                      <td>{pretty(r.triggerType)}</td>
                      <td className="wrap">{prettyList(r.faults)}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {r.beforeStatus} to {r.afterStatus}
                      </td>
                      <td>
                        <Chip tone={VERDICT[r.verdict]?.tone}>
                          {VERDICT[r.verdict]?.label || r.verdict}
                        </Chip>
                      </td>
                      <td>
                        <button className="linkbtn" onClick={() => setReport(r)}>
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {history.length === 0 && (
                <p className="empty">No recoveries yet. Choose Failure, then run self-healing.</p>
              )}
            </div>
          </section>

          <section className="panel panel-pad">
            <div className="panel-head">
              <h2 className="panel-title">Email alerts</h2>
              <button
                className="btn-quiet"
                style={{ padding: "5px 12px", fontSize: 13 }}
                disabled={!online || emailTestPending}
                onClick={sendEmailTest}
              >
                {emailTestPending ? "Sending..." : "Send test email"}
              </button>
            </div>
            {emailTestResult && (
              <p className="small muted" aria-live="polite" style={{ marginBottom: 12 }}>
                {emailTestResult}
              </p>
            )}
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Email</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {notifications.map((n) => (
                    <tr key={n.id}>
                      <td className="time">{time(n.createdAt)}</td>
                      <td>{MAIL_TYPE[n.type] || pretty(n.type)}</td>
                      <td>
                        <Chip tone={MAIL[n.status]?.tone}>
                          {MAIL[n.status]?.label || n.status}
                        </Chip>
                        {n.error && (
                          <small className="small muted" style={{ display: "block" }}>
                            {n.error}
                          </small>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {notifications.length === 0 && (
                <p className="empty">No emails yet. They are sent when a problem is found.</p>
              )}
            </div>
          </section>
        </div>
      </main>

      <Report record={report} onClose={() => setReport(null)} />
    </div>
  );
}