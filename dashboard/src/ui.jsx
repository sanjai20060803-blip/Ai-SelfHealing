// Small shared pieces used by every part of the dashboard.

export const time = (iso) => (iso ? new Date(iso).toLocaleTimeString() : "–");

export const clock = (iso) =>
  iso
    ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

export const round1 = (v) =>
  v === null || v === undefined || Number.isNaN(Number(v))
    ? "–"
    : (Math.round(Number(v) * 10) / 10).toLocaleString();

export const pretty = (text) => {
  if (!text) return "–";
  const s = String(text).replaceAll("_", " ").toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
};

export const prettyList = (text) =>
  !text
    ? "–"
    : String(text)
        .split(",")
        .map((p) => pretty(p.trim()))
        .join(", ");

// Status -> tone, plain-language label
export const STATUS = {
  Normal: { tone: "good", word: "Healthy" },
  Abnormal: { tone: "warn", word: "Unstable" },
  Failure: { tone: "bad", word: "Failing" },
};

export const VERDICT = {
  HEALED: { tone: "good", label: "Healed" },
  PARTIAL: { tone: "warn", label: "Partly healed" },
  FAILED: { tone: "bad", label: "Failed" },
  NOT_NEEDED: { tone: "neutral", label: "Not needed" },
};

export const MAIL = {
  SENT: { tone: "good", label: "Sent" },
  FAILED: { tone: "bad", label: "Failed" },
  SKIPPED: { tone: "neutral", label: "Skipped" },
};

export const MAIL_TYPE = {
  ISSUE_DETECTED: "Issue detected",
  RECOVERY_RESULT: "Recovery result",
  EARLY_WARNING: "Early warning",
  TEST: "Test email",
};

function Icon({ tone }) {
  const common = {
    width: 14,
    height: 14,
    viewBox: "0 0 14 14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
  if (tone === "good")
    return (
      <svg {...common}>
        <path d="M2.5 7.4 5.6 10.5 11.5 3.8" />
      </svg>
    );
  if (tone === "warn")
    return (
      <svg {...common}>
        <path d="M7 2 12.5 11.5h-11z" />
        <path d="M7 6v2.6M7 10.2v.1" />
      </svg>
    );
  if (tone === "bad")
    return (
      <svg {...common}>
        <path d="m3.5 3.5 7 7M10.5 3.5l-7 7" />
      </svg>
    );
  return (
    <svg {...common}>
      <path d="M3.5 7h7" />
    </svg>
  );
}

export function Chip({ tone = "neutral", children }) {
  return (
    <span className={"chip tone-" + tone}>
      <Icon tone={tone} />
      {children}
    </span>
  );
}

// A thin line that shows how a number moved over the last readings.
export function Spark({ values, color = "var(--brand)" }) {
  const w = 52;
  const h = 22;
  const pad = 2.5;
  if (!values || values.length < 2) return <svg width={w} height={h} aria-hidden="true" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [
    pad + (i * (w - 2 * pad)) / (values.length - 1),
    h - pad - ((v - min) / span) * (h - 2 * pad),
  ]);
  const d = pts.map(([x, y], i) => (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1)).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg width={w} height={h} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lx} cy={ly} r="2.4" fill={color} stroke="#fff" strokeWidth="1.2" />
    </svg>
  );
}

// One bar split into parts, with a legend that carries the numbers.
export function StackBar({ parts }) {
  const total = parts.reduce((a, p) => a + p.value, 0);
  return (
    <div>
      <div className="stack" role="img" aria-label={parts.map((p) => `${p.label} ${p.text}`).join(", ")}>
        {parts.map((p) =>
          p.value > 0 ? (
            <span key={p.label} style={{ flexGrow: p.value, background: p.color }} />
          ) : null,
        )}
        {total === 0 && <span style={{ flexGrow: 1, background: "var(--line-soft)" }} />}
      </div>
      <div className="stack-legend">
        {parts.map((p) => (
          <span key={p.label}>
            <i className="swatch" style={{ background: p.color }} />
            {p.label} {p.text}
          </span>
        ))}
      </div>
    </div>
  );
}

// Tooltip used by every chart.
export function ChartTip({ active, payload, label, unit = "" }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="tip">
      <div className="tip-time">{label}</div>
      {payload.map((p) => (
        <div className="tip-row" key={p.dataKey}>
          <i className="swatch" style={{ background: p.color }} />
          {p.name}
          <b>
            {round1(p.value)}
            {unit}
          </b>
        </div>
      ))}
    </div>
  );
}