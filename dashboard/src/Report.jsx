import { useEffect } from "react";
import { Chip, VERDICT, pretty, prettyList, round1 } from "./ui";

const when = (iso) => (iso ? new Date(iso).toLocaleString() : "–");

const acr = (t) => pretty(t).replace(/\b(ip|dns|dhcp|tcp|wifi)\b/gi, (m) => (m.toLowerCase() === "wifi" ? "Wi-Fi" : m.toUpperCase()));

const csvCell = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;

// Downloads the whole recovery history as a CSV file that opens in Excel.
export function downloadCsv(history) {
  const cols = [
    ["id", "ID"],
    ["createdAt", "Time"],
    ["triggerType", "Started by"],
    ["mode", "Run mode"],
    ["severity", "Severity"],
    ["faults", "Problems found"],
    ["actions", "Repair actions"],
    ["beforeStatus", "Status before"],
    ["afterStatus", "Status after"],
    ["beforeLatency", "Latency before (ms)"],
    ["afterLatency", "Latency after (ms)"],
    ["beforeLoss", "Packet loss before (%)"],
    ["afterLoss", "Packet loss after (%)"],
    ["beforeBandwidth", "Bandwidth before (Mbps)"],
    ["afterBandwidth", "Bandwidth after (Mbps)"],
    ["verdict", "Outcome"],
  ];
  const lines = [cols.map((c) => csvCell(c[1])).join(",")];
  for (const r of history) {
    lines.push(cols.map((c) => csvCell(r[c[0]])).join(","));
  }
  const blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `recovery-history-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function change(before, after, lowerIsBetter) {
  const b = Number(before);
  const a = Number(after);
  if (!b) return { text: "–", tone: "neutral" };
  const pct = ((a - b) / b) * 100;
  const better = lowerIsBetter ? pct < 0 : pct > 0;
  return {
    text: `${pct > 0 ? "+" : "−"}${Math.abs(Math.round(pct)).toLocaleString()}%`,
    tone: pct === 0 ? "neutral" : better ? "good" : "bad",
  };
}

// A printable incident report for one recovery. "Print" lets the user save it as a PDF.
export default function Report({ record: r, onClose }) {
  useEffect(() => {
    if (!r) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [r, onClose]);

  if (!r) return null;

  const verdict = VERDICT[r.verdict] || { tone: "neutral", label: r.verdict };
  const actions = String(r.actions || "")
    .split(/[,;|]/)
    .map((a) => a.trim())
    .filter(Boolean);
  const simulated = /sim/i.test(String(r.mode || ""));

  const summary =
    `At ${when(r.createdAt)}, the AI found the network ${String(r.beforeStatus || "").toLowerCase()}. ` +
    `Problems found: ${prettyList(r.faults).toLowerCase()}. ` +
    (actions.length
      ? `${actions.length} repair action${actions.length > 1 ? "s were" : " was"} ${simulated ? "simulated" : "run"}. `
      : "No repair action was needed. ") +
    `Afterwards the network was ${String(r.afterStatus || "").toLowerCase()}, so the outcome is "${verdict.label.toLowerCase()}".`;

  const rows = [
    ["Latency", "ms", r.beforeLatency, r.afterLatency, true],
    ["Packet loss", "%", r.beforeLoss, r.afterLoss, true],
    ["Bandwidth", "Mbps", r.beforeBandwidth, r.afterBandwidth, false],
  ];

  return (
    <div className="report-overlay" role="dialog" aria-modal="true" aria-label="Incident report">
      <div className="report-sheet">
        <div className="report-tools no-print">
          <button className="btn-primary" style={{ marginLeft: 0 }} onClick={() => window.print()}>
            Print or save as PDF
          </button>
          <button className="btn-quiet" onClick={onClose}>
            Close
          </button>
        </div>

        <header className="report-head">
          <div>
            <h2 className="report-title">Incident report</h2>
            <p className="muted">
              Recovery number {r.id}, {when(r.createdAt)}
            </p>
          </div>
          <Chip tone={verdict.tone}>{verdict.label}</Chip>
        </header>

        <p className="report-summary">{summary}</p>

        <dl className="report-facts">
          <div>
            <dt>Started by</dt>
            <dd>{pretty(r.triggerType)}</dd>
          </div>
          <div>
            <dt>Run mode</dt>
            <dd>{simulated ? "Simulated repair" : pretty(r.mode)}</dd>
          </div>
          <div>
            <dt>Severity</dt>
            <dd>{pretty(r.severity)}</dd>
          </div>
          <div>
            <dt>Network status</dt>
            <dd>
              {r.beforeStatus} to {r.afterStatus}
            </dd>
          </div>
        </dl>

        <h3 className="report-h">Problems found</h3>
        <p>{prettyList(r.faults)}</p>

        <h3 className="report-h">Repair actions</h3>
        {actions.length ? (
          <ol className="report-actions">
            {actions.map((a) => (
              <li key={a}>{acr(a)}</li>
            ))}
          </ol>
        ) : (
          <p>None. The network did not need repair.</p>
        )}

        <h3 className="report-h">Before and after</h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Reading</th>
              <th>Before</th>
              <th>After</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, unit, b, a, lower]) => {
              const c = change(b, a, lower);
              return (
                <tr key={name}>
                  <td>{name}</td>
                  <td>
                    {round1(b)} {unit}
                  </td>
                  <td>
                    {round1(a)} {unit}
                  </td>
                  <td>
                    <span className={"chip tone-" + c.tone}>{c.text}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {r.advice && (
          <>
            <h3 className="report-h">Advice</h3>
            <p>{r.advice}</p>
          </>
        )}

        <p className="small muted report-foot">
          Created by Self-Healing Network on {when(new Date().toISOString())}.{" "}
          {simulated
            ? "This repair was simulated, so the numbers show the demo scenario, not a real network."
            : "The numbers were measured on this computer."}
        </p>
      </div>
    </div>
  );
}