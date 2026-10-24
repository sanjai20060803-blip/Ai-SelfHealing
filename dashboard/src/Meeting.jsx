import { useEffect, useState } from "react";
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
import { ChartTip, Chip, time } from "./ui";

const MODE_TITLE = {
  HD_VIDEO: "HD video is fine",
  VIDEO: "Standard video",
  AUDIO_ONLY: "Audio only",
  NOT_READY: "Not ready to join",
};

// Zones of the MOS scale, 1 to 4.5
const MIN = 1;
const MAX = 4.5;
const pos = (v) => ((v - MIN) / (MAX - MIN)) * 100;

const ratingTone = (mos) => (mos >= 3.6 ? "good" : mos >= 2.6 ? "warn" : "bad");

function PlatformChip({ p }) {
  if (p.pending) return <Chip>Checking</Chip>;
  if (!p.reachable) return <Chip tone="bad">Unreachable</Chip>;
  if (p.connectMs > 250) return <Chip tone="warn">Slow, {p.connectMs} ms</Chip>;
  return <Chip tone="good">Reachable, {p.connectMs} ms</Chip>;
}

export default function Meeting() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await api.get("/meeting/status");
        if (alive) setData(res.data);
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

  // The switch always does what it says: if class mode is on it turns it off, and the other way round.
  async function setClassMode(mode) {
    try {
      const res = await api.post(`/meeting/class-mode/${mode}`);
      setData(res.data);
    } catch (e) {
      console.error(e);
    }
  }

  if (!data) return null;

  const q = data.quality;
  const cls = data.classMode || {};
  const apps = cls.detectedApps || [];
  const history = (data.history || []).map((h) => ({ full: time(h.time), mos: h.mos }));
  const simulated = (data.platforms || []).some((p) => p.simulated);

  return (
    <section className="panel meeting" aria-label="Meeting readiness">
      <div className="cell">
        <div className="panel-head">
          <h2 className="panel-title">Meeting quality</h2>
          {q && <Chip tone={ratingTone(q.mos)}>{q.rating}</Chip>}
        </div>

        {q ? (
          <>
            <div className="mos">
              <span className="mos-num">{q.mos.toFixed(1)}</span>
              <span className="muted">out of 4.5</span>
            </div>

            <div className="meter-wrap" style={{ marginTop: 14 }}>
              <div className="meter" role="img" aria-label={`Meeting quality ${q.mos} out of 4.5`}>
                <i style={{ width: pos(2.6) + "%", background: "var(--bad-bg)" }} />
                <i style={{ width: pos(3.6) - pos(2.6) + "%", background: "var(--warn-bg)" }} />
                <i style={{ width: 100 - pos(3.6) + "%", background: "var(--good-bg)" }} />
              </div>
              <span
                className="meter-marker"
                style={{ left: Math.max(0, Math.min(100, pos(q.mos))) + "%" }}
              />
              <div className="meter-scale" aria-hidden="true">
                <span style={{ left: 0 }}>1</span>
                <span style={{ left: pos(2.6) + "%" }}>2.6</span>
                <span style={{ left: pos(3.6) + "%" }}>3.6</span>
                <span style={{ left: "100%" }}>4.5</span>
              </div>
            </div>

            <p className="mode-title">{MODE_TITLE[q.mode] || q.mode}</p>
            <p className="lede" style={{ marginTop: 4 }}>
              {q.summary}
            </p>
          </>
        ) : (
          <p className="muted">Waiting for the first reading.</p>
        )}
      </div>

      <div className="cell">
        <div className="panel-head">
          <h2 className="panel-title">What to do before joining</h2>
        </div>
        {q && (
          <ul className="tips">
            {q.tips.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        )}
        <p className="small muted" style={{ margin: "16px 0 4px" }}>
          Quality over the last readings
        </p>
        <div style={{ height: 96 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history} margin={{ top: 6, right: 6, left: 6, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#edf0f5" />
              <XAxis dataKey="full" hide />
              <YAxis domain={[1, 4.5]} hide />
              <Tooltip
                content={<ChartTip />}
                cursor={{ stroke: "#9aa6ba", strokeDasharray: "3 3" }}
              />
              <Line
                type="monotone"
                dataKey="mos"
                name="Quality"
                stroke="var(--s-latency)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="cell">
        <div className="panel-head">
          <h2 className="panel-title">Meeting servers</h2>
        </div>
        <div>
          {(data.platforms || []).map((p) => (
            <div className="plat" key={p.platform}>
              <div>
                <div style={{ fontWeight: 600 }}>{p.platform}</div>
                <div className="small muted">{p.host}</div>
              </div>
              <PlatformChip p={p} />
            </div>
          ))}
        </div>
        <p className="small muted" style={{ marginTop: 12 }}>
          {simulated
            ? "Simulated in Simulation mode. Switch to Real network to test the real servers."
            : "Opens a connection to each service every 30 seconds. Nothing is sent and no login is used."}
        </p>
      </div>

      <div className="cell meeting-foot">
        <button
          className="switch"
          role="switch"
          aria-checked={!!cls.active}
          onClick={() => setClassMode(cls.active ? "off" : "on")}
          title="Turn class mode on or off"
        >
          <span className="switch-track" />
          <span>
            <b>Class mode {cls.active ? "on" : "off"}</b>
            <span className="muted">
              {cls.active
                ? ". Problems are repaired automatically."
                : cls.mode === "off"
                  ? ". You turned it off."
                  : ". Turns on by itself when Zoom, Teams or Webex is running on this computer."}
            </span>
          </span>
        </button>
        <span className="small muted">
          {apps.length > 0
            ? "Found on this computer: " + apps.join(", ") + ". "
            : "No meeting app found. A Google Meet tab in a browser can't be detected, so use the switch. "}
          {cls.mode && cls.mode !== "auto" && (
            <button className="linkbtn" onClick={() => setClassMode("auto")}>
              Go back to automatic
            </button>
          )}
        </span>
      </div>
    </section>
  );
}