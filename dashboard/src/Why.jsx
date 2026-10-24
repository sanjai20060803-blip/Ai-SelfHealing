import { useEffect, useState } from "react";
import api from "./api";

const withUnit = (v, unit) => (unit === "%" ? `${v}%` : unit ? `${v} ${unit}` : `${v}`);

function sentence(r) {
  if (r.feature === "connected") return "The connection is down";
  const where = r.direction === "higher" ? "above" : "below";
  return `${r.label} is ${withUnit(r.value, r.unit)}, ${where} the usual ${withUnit(r.typical, r.unit)}`;
}

// Opens a short explanation of the AI's latest answer.
export default function Why() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    const load = async () => {
      try {
        const res = await api.get("/explain/latest");
        if (alive) {
          setData(res.data || null);
          setFailed(false);
        }
      } catch {
        if (alive) setFailed(true);
      }
    };
    load();
    const timer = setInterval(load, 4000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [open]);

  const reasons = data?.reasons || [];

  return (
    <div className="why">
      <button className="why-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path
            d={open ? "M3 8.5 7 4.5l4 4" : "M3 5.5 7 9.5l4-4"}
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Why this result?
      </button>

      {open && (
        <div className="why-body">
          {failed && !data && (
            <p className="muted">
              The AI service did not answer. Check that the AI service window is running.
            </p>
          )}
          {!failed && !data && <p className="muted">Asking the AI…</p>}

          {data && reasons.length === 0 && (
            <p>Every reading is inside its normal range, so nothing pushed the result away from Normal.</p>
          )}

          {data && reasons.length > 0 && (
            <>
              <p className="why-title">
                {data.status === "Normal"
                  ? "The status is healthy, but these readings are worth watching:"
                  : `What pushed the AI toward ${data.status}:`}
              </p>
              <ul className="why-list">
                {reasons.map((r) => (
                  <li key={r.feature}>
                    <div className="why-row">
                      <span>{sentence(r)}</span>
                      <b>{r.share_pct}%</b>
                    </div>
                    <div className="why-track">
                      <i style={{ width: r.share_pct + "%" }} />
                    </div>
                  </li>
                ))}
              </ul>
              <p className="small muted">
                How this is worked out: each reading is swapped for a typical healthy value to see how
                much the AI's answer changes. The percentages are shares of the top reasons.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}