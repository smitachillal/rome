import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";
import {
  User, Activity, Pill, ShieldAlert, AlertTriangle, GitCompareArrows,
  Sparkles, FileText, HeartPulse, Droplets, LoaderCircle, RefreshCw,
  Layers, CircleCheck, Inbox,
} from "lucide-react";

/* ==================================================================
 *  API — one endpoint per section. Change API_BASE / patientId props.
 *  Expected JSON per endpoint (all fields optional, panels degrade):
 *
 *  personal      -> { name, age, sex, weight_kg, ckd_status, ckd_stage }
 *  renal-trajectory -> { points:[{date,egfr,crcl}], aki, ckd_stage }   (or a bare array of points)
 *  renal-drugs   -> [{ name, flag:"danger"|"warning"|"ok", note }]     (or ["morphine", ...])
 *  drug-history  -> [{ start_time, stop_time, route, drug_type, drug,
 *                      product_strength, dose_value, dose_unit, form_unit, doses_24h }]
 *  suggested-medication -> [{ drug, rationale }]                       (or { suggestions:[...] })
 *  risk-score    -> { score:0..1, band, contributions:[{feature,value}] }
 *  alerts        -> [{ severity:"danger"|"warning"|"info", message }]  (or [] for none)
 *  interactions  -> [{ drug_a, drug_b, issue, action, source }]
 *  explanation   -> { text }                                           (or a bare string)
 * ================================================================== */
const buildEndpoints = (base, id) => ({
  personal:     `${base}/patients/${id}/personal`,
  trajectory:   `${base}/patients/${id}/renal-trajectory`,
  renalDrugs:   `${base}/patients/${id}/renal-drugs`,
  drugHistory:  `${base}/patients/${id}/drug-history`,
  suggested:    `${base}/patients/${id}/suggested-medication`,
  risk:         `${base}/patients/${id}/risk-score`,
  alerts:       `${base}/patients/${id}/alerts`,
  interactions: `${base}/patients/${id}/interactions`,
  explanation:  `${base}/patients/${id}/explanation`,
});

function useJson(url) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  useEffect(() => {
    if (!url) return;
    let alive = true;
    setState((s) => ({ ...s, status: "loading", error: null }));
    fetch(url)
      .then(async (r) => {
        const text = await r.text();
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return text ? JSON.parse(text) : null;
      })
      .then((data) => alive && setState({ status: "ready", data, error: null }))
      .catch((e) => alive && setState({ status: "error", data: null, error: e.message }));
    return () => { alive = false; };
  }, [url, nonce]);
  return { ...state, reload };
}

/* ==================================================================
 *  Theme — shared clinical instrument palette
 * ================================================================== */
const T = {
  bg: "#E7EDEB", panel: "#FFFFFF", ink: "#0E2A2C", sub: "#5C7477", faint: "#93A9AA",
  line: "#DBE5E3", teal: "#0F766E", tealDeep: "#0A544D", tealSoft: "#D2E8E4",
  amber: "#D69A2D", amberSoft: "#F7ECD3", amberInk: "#7A5410",
  coral: "#CD5540", coralSoft: "#F3DAD3", coralInk: "#8A2E1E",
  green: "#3E8E5B", greenSoft: "#DCEEE1", blue: "#3E7CA8",
};
const display = "'Space Grotesk', system-ui, sans-serif";
const body = "'Inter', system-ui, sans-serif";
const mono = "'IBM Plex Mono', ui-monospace, monospace";

const TONE = {
  danger:  { bg: T.coralSoft, fg: T.coralInk, dot: T.coral },
  warning: { bg: T.amberSoft, fg: T.amberInk, dot: T.amber },
  ok:      { bg: T.tealSoft,  fg: T.tealDeep, dot: T.teal },
  info:    { bg: "#E4EEF3",   fg: "#2C5670",  dot: T.blue },
};

/* Fallback flags when the API sends plain drug names.
   Real CDSS logic should live in the backend — this only styles the chip. */
const FALLBACK_FLAG = {
  vancomycin: "danger", digoxin: "warning", gabapentin: "warning",
  spironolactone: "warning", morphine: "ok",
};

/* ==================================================================
 *  Primitives
 * ================================================================== */
function Panel({ title, icon: Icon, hint, children, action, style }) {
  return (
    <section style={{ background: T.panel, borderRadius: 14, border: `1px solid ${T.line}`,
      boxShadow: "0 1px 2px rgba(14,42,44,0.04)", padding: 18, display: "flex",
      flexDirection: "column", ...style }}>
      {title && (
        <header style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          {Icon && (
            <span style={{ display: "grid", placeItems: "center", width: 28, height: 28,
              borderRadius: 8, background: T.tealSoft, color: T.tealDeep, flexShrink: 0 }}>
              <Icon size={15} strokeWidth={2.2} />
            </span>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 style={{ margin: 0, fontFamily: display, fontSize: 14.5, fontWeight: 600,
              letterSpacing: "-0.01em", color: T.ink }}>{title}</h2>
            {hint && <p style={{ margin: "2px 0 0", fontFamily: body, fontSize: 11.5, color: T.faint }}>{hint}</p>}
          </div>
          {action}
        </header>
      )}
      <div style={{ flex: 1 }}>{children}</div>
    </section>
  );
}

function Skeleton({ h = 80 }) {
  return <div className="pulse" style={{ height: h, borderRadius: 8, background: T.line }} />;
}

function EmptyState({ icon: Icon = Inbox, text }) {
  return (
    <div style={{ display: "grid", placeItems: "center", gap: 8, padding: "22px 0", textAlign: "center" }}>
      <Icon size={22} color={T.faint} />
      <p style={{ margin: 0, fontFamily: body, fontSize: 12.5, color: T.faint }}>{text}</p>
    </div>
  );
}

function ErrorState({ error, onRetry }) {
  return (
    <div style={{ display: "grid", placeItems: "center", gap: 10, padding: "18px 0", textAlign: "center" }}>
      <AlertTriangle size={20} color={T.coral} />
      <p style={{ margin: 0, fontFamily: body, fontSize: 12.5, color: T.coralInk }}>
        Couldn’t load this section — {error}
      </p>
      <button onClick={onRetry} style={{ display: "inline-flex", alignItems: "center", gap: 6,
        cursor: "pointer", fontFamily: body, fontSize: 12, color: T.tealDeep, background: T.tealSoft,
        border: "none", padding: "5px 12px", borderRadius: 999 }}>
        <RefreshCw size={13} /> Retry
      </button>
    </div>
  );
}

/* Renders loading / error / empty / ready around a data-driven body */
function Body({ state, isEmpty, empty, skeletonH = 80, children }) {
  if (state.status === "loading") return <Skeleton h={skeletonH} />;
  if (state.status === "error") return <ErrorState error={state.error} onRetry={state.reload} />;
  const data = state.data;
  const blank = isEmpty ? isEmpty(data) : (data == null || (Array.isArray(data) && data.length === 0));
  if (blank) return empty;
  return children(data);
}

function Chip({ children, tone = "ok", title }) {
  const t = TONE[tone] || TONE.ok;
  return (
    <span title={title} style={{ display: "inline-flex", alignItems: "center", gap: 6,
      fontFamily: body, fontSize: 12.5, padding: "6px 12px", borderRadius: 999,
      background: t.bg, color: t.fg }}>
      {tone !== "ok" && <span style={{ width: 6, height: 6, borderRadius: "50%", background: t.dot }} />}
      {children}
    </span>
  );
}

function TT({ rows }) {
  return (
    <div style={{ background: T.ink, color: "#fff", borderRadius: 8, padding: "8px 10px",
      fontFamily: mono, fontSize: 11.5, boxShadow: "0 6px 20px rgba(0,0,0,0.2)" }}>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", gap: 18 }}>
          <span style={{ color: T.faint }}>{r[0]}</span><span>{r[1]}</span>
        </div>
      ))}
    </div>
  );
}

/* ==================================================================
 *  Normalisers
 * ================================================================== */
function normTraj(d) {
  const points = Array.isArray(d) ? d : (d?.points || []);
  const pts = points.map((p, i) => ({ i, date: p.date ?? i, egfr: p.egfr, crcl: p.crcl }));
  const last = pts[pts.length - 1] || {};
  return {
    pts,
    latestEgfr: d?.latest_egfr ?? last.egfr,
    latestCrcl: d?.latest_crcl ?? last.crcl,
    ckdStage: d?.ckd_stage,
    aki: d?.aki,
  };
}
function normDrugs(d) {
  const arr = Array.isArray(d) ? d : (d?.drugs || []);
  return arr.map((x) => {
    if (typeof x === "string") return { name: x, flag: FALLBACK_FLAG[x.toLowerCase()] || "ok", note: null };
    return { name: x.name, flag: x.flag || FALLBACK_FLAG[(x.name || "").toLowerCase()] || "ok", note: x.note };
  });
}
function normRisk(d) {
  if (!d) return null;
  const score = d.score ?? d.value ?? 0;
  const band = d.band || (score >= 0.66 ? "High" : score >= 0.33 ? "Moderate" : "Low");
  const contributions = (d.contributions || d.shap || []).map((c) => ({
    feature: c.feature ?? c.name, value: c.value ?? c.importance,
  }));
  return { score, band, contributions };
}
const bandTone = (band) => (band === "High" ? "danger" : band === "Moderate" ? "warning" : "ok");

/* ==================================================================
 *  Banner + KPI row
 * ================================================================== */
function Banner({ personal, risk, patientId }) {
  const p = personal.data || {};
  const r = normRisk(risk.data);
  const initial = (p.name || `Patient ${patientId}`).replace(/[^A-Za-z]/g, "").charAt(0) || "P";
  const loading = personal.status === "loading";
  return (
    <header style={{ background: T.panel, border: `1px solid ${T.line}`, borderRadius: 16,
      padding: "16px 20px", display: "flex", flexWrap: "wrap", gap: 16,
      justifyContent: "space-between", alignItems: "center", boxShadow: "0 1px 2px rgba(14,42,44,0.04)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ display: "grid", placeItems: "center", width: 50, height: 50, borderRadius: "50%",
          background: T.teal, color: "#fff", fontFamily: display, fontSize: 20, fontWeight: 600 }}>{initial}</span>
        <div>
          <h1 style={{ margin: 0, fontFamily: display, fontSize: "clamp(19px,2.5vw,24px)", fontWeight: 700,
            letterSpacing: "-0.02em", color: T.ink }}>{p.name || `Patient ${patientId}`}</h1>
          <p style={{ margin: "3px 0 0", fontFamily: body, fontSize: 13, color: T.sub }}>
            {loading ? "Loading patient…" :
              [p.age != null && `${p.age} years`, p.sex, p.weight_kg != null && `${p.weight_kg} kg`]
                .filter(Boolean).join(" · ") || "—"}
          </p>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {p.ckd_status && (
          <Chip tone="warning" title="Chronic kidney disease">
            {p.ckd_status}{p.ckd_stage ? ` · stage ${p.ckd_stage}` : ""}
          </Chip>
        )}
        {r && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: body,
            fontSize: 12.5, fontWeight: 500, padding: "6px 12px", borderRadius: 999,
            background: TONE[bandTone(r.band)].bg, color: TONE[bandTone(r.band)].fg }}>
            <ShieldAlert size={14} /> {r.band} risk · {r.score.toFixed(2)}
          </span>
        )}
      </div>
    </header>
  );
}

function KpiRow({ traj, renalDrugs, alerts }) {
  const t = traj.status === "ready" ? normTraj(traj.data) : {};
  const drugCount = renalDrugs.status === "ready" ? normDrugs(renalDrugs.data).length : null;
  const flagCount = alerts.status === "ready" ? (alerts.data?.length ?? 0) : null;
  const fmt = (v, unit) => v == null ? "—" : <>{v}<span style={{ fontSize: 12, color: T.faint }}> {unit}</span></>;
  const cards = [
    { label: "eGFR", value: fmt(t.latestEgfr, "mL/min"), icon: HeartPulse,
      tone: t.latestEgfr != null && t.latestEgfr < 30 ? T.amber : T.teal, loading: traj.status === "loading" },
    { label: "CrCl", value: fmt(t.latestCrcl, "mL/min"), icon: Droplets, tone: T.teal, loading: traj.status === "loading" },
    { label: "Renal drugs", value: drugCount ?? "—", icon: Pill, tone: T.tealDeep, loading: renalDrugs.status === "loading" },
    { label: "Open flags", value: flagCount ?? "—", icon: AlertTriangle,
      tone: flagCount ? T.coral : T.green, loading: alerts.status === "loading" },
  ];
  return (
    <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
      {cards.map((c) => (
        <div key={c.label} style={{ background: T.panel, border: `1px solid ${T.line}`, borderRadius: 12,
          padding: "14px 16px", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: c.tone }} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontFamily: body, fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em",
              color: T.sub, fontWeight: 600 }}>{c.label}</span>
            <c.icon size={15} color={c.tone} strokeWidth={2.2} />
          </div>
          {c.loading
            ? <div className="pulse" style={{ height: 26, width: "60%", borderRadius: 6, background: T.line }} />
            : <div style={{ fontFamily: mono, fontSize: 25, fontWeight: 500, color: T.ink, lineHeight: 1 }}>{c.value}</div>}
        </div>
      ))}
    </div>
  );
}

/* ==================================================================
 *  Detail panels
 * ================================================================== */
function TrendPanel({ state }) {
  return (
    <Panel title="Renal function trend" icon={Activity} hint="eGFR & creatinine clearance over time" style={{ gridColumn: "span 2" }}>
      <Body state={state} skeletonH={210}
        isEmpty={(d) => normTraj(d).pts.length === 0}
        empty={<EmptyState icon={Activity} text="No renal readings recorded" />}>
        {(d) => {
          const { pts } = normTraj(d);
          return (
            <>
              <ResponsiveContainer width="100%" height={210}>
                <LineChart data={pts} margin={{ top: 6, right: 12, bottom: 0, left: -18 }}>
                  <CartesianGrid stroke={T.line} strokeDasharray="2 4" />
                  <XAxis dataKey="date" tick={{ fontFamily: mono, fontSize: 9.5, fill: T.faint }} minTickGap={24} />
                  <YAxis tick={{ fontFamily: mono, fontSize: 9.5, fill: T.faint }} />
                  <Tooltip content={({ active, payload }) => active && payload?.length
                    ? <TT rows={payload.map((p) => [p.name, p.value])} /> : null} />
                  <Line type="monotone" dataKey="egfr" name="eGFR" stroke={T.teal} strokeWidth={2.2} dot={false} />
                  <Line type="monotone" dataKey="crcl" name="CrCl" stroke={T.blue} strokeWidth={2.2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", gap: 16, marginTop: 4, fontFamily: body, fontSize: 11.5, color: T.sub }}>
                <span><span style={{ display: "inline-block", width: 10, height: 2, background: T.teal, verticalAlign: "middle", marginRight: 6 }} />eGFR</span>
                <span><span style={{ display: "inline-block", width: 10, height: 2, background: T.blue, verticalAlign: "middle", marginRight: 6 }} />CrCl</span>
              </div>
            </>
          );
        }}
      </Body>
    </Panel>
  );
}

function RiskPanel({ state }) {
  return (
    <Panel title="Risk score" icon={ShieldAlert} hint="SHAP model output">
      <Body state={state} skeletonH={180} isEmpty={(d) => !normRisk(d)}
        empty={<EmptyState icon={ShieldAlert} text="No risk score available" />}>
        {(d) => {
          const r = normRisk(d);
          const a = Math.PI * (1 - r.score);
          const x = 50 + 40 * Math.cos(a), y = 55 - 40 * Math.sin(a);
          const big = r.score > 0.5 ? 1 : 0;
          const tone = TONE[bandTone(r.band)];
          return (
            <div>
              <div style={{ textAlign: "center" }}>
                <svg viewBox="0 0 100 62" width="150" height="93" role="img" aria-label={`Risk ${r.score.toFixed(2)}`}>
                  <path d="M10,55 A40,40 0 0,1 90,55" fill="none" stroke={T.line} strokeWidth="9" strokeLinecap="round" />
                  <path d={`M10,55 A40,40 0 ${big},1 ${x.toFixed(1)},${y.toFixed(1)}`} fill="none" stroke={tone.dot} strokeWidth="9" strokeLinecap="round" />
                </svg>
                <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 500, color: T.ink, marginTop: -6 }}>{r.score.toFixed(2)}</div>
                <div style={{ fontFamily: body, fontSize: 12, color: tone.fg, fontWeight: 500 }}>{r.band} risk</div>
              </div>
              {r.contributions.length > 0 && (
                <div style={{ marginTop: 14, borderTop: `1px solid ${T.line}`, paddingTop: 12 }}>
                  <p style={{ margin: "0 0 8px", fontFamily: body, fontSize: 11, color: T.faint, textTransform: "uppercase", letterSpacing: "0.05em" }}>Top drivers</p>
                  {r.contributions.slice(0, 4).map((c) => {
                    const max = Math.max(...r.contributions.map((x) => Math.abs(x.value))) || 1;
                    return (
                      <div key={c.feature} style={{ display: "grid", gap: 4, marginBottom: 8 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: body, fontSize: 11.5, color: T.sub }}>
                          <span>{c.feature}</span><span style={{ fontFamily: mono }}>{Number(c.value).toFixed(2)}</span>
                        </div>
                        <div style={{ height: 5, background: T.line, borderRadius: 999 }}>
                          <div style={{ width: `${(Math.abs(c.value) / max) * 100}%`, height: "100%",
                            background: c.value >= 0 ? T.coral : T.teal, borderRadius: 999 }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        }}
      </Body>
    </Panel>
  );
}

function RenalDrugsPanel({ state }) {
  return (
    <Panel title="Renal drugs" icon={Pill} hint="Current renally-relevant medications">
      <Body state={state} isEmpty={(d) => normDrugs(d).length === 0}
        empty={<EmptyState icon={Pill} text="No renal drugs on record" />}>
        {(d) => (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {normDrugs(d).map((x) => (
              <Chip key={x.name} tone={x.flag} title={x.note || undefined}>{x.name}</Chip>
            ))}
          </div>
        )}
      </Body>
    </Panel>
  );
}

function AlertsPanel({ state }) {
  return (
    <Panel title="Alerts & flags" icon={AlertTriangle}>
      <Body state={state}
        empty={<EmptyState icon={CircleCheck} text="No alerts raised for this patient" />}>
        {(d) => (
          <div style={{ display: "grid", gap: 8 }}>
            {d.map((a, i) => {
              const t = TONE[a.severity] || TONE.info;
              return (
                <div key={i} style={{ borderLeft: `3px solid ${t.dot}`, background: t.bg,
                  padding: "8px 12px", borderRadius: "0 8px 8px 0" }}>
                  <p style={{ margin: 0, fontFamily: body, fontSize: 12.5, color: T.ink }}>{a.message || a.text}</p>
                </div>
              );
            })}
          </div>
        )}
      </Body>
    </Panel>
  );
}

function InteractionsPanel({ state }) {
  return (
    <Panel title="Possible medication issues" icon={GitCompareArrows} hint="Drug–drug interaction details">
      <Body state={state}
        empty={<EmptyState icon={CircleCheck} text="No interactions detected" />}>
        {(d) => (
          <div style={{ display: "grid", gap: 10 }}>
            {d.map((x, i) => (
              <div key={i} style={{ border: `1px solid ${T.line}`, borderRadius: 10, padding: "10px 12px" }}>
                <p style={{ margin: 0, fontFamily: body, fontSize: 13, fontWeight: 500, color: T.ink }}>
                  {x.drug_a} × {x.drug_b}
                </p>
                {x.issue && <p style={{ margin: "3px 0 0", fontFamily: body, fontSize: 12, color: T.sub }}>{x.issue}</p>}
                {x.action && <p style={{ margin: "3px 0 0", fontFamily: body, fontSize: 12, color: T.coralInk }}>→ {x.action}</p>}
                {x.source && <p style={{ margin: "5px 0 0", fontFamily: mono, fontSize: 10.5, color: T.faint }}>source: {x.source}</p>}
              </div>
            ))}
          </div>
        )}
      </Body>
    </Panel>
  );
}

function SuggestedPanel({ state }) {
  const norm = (d) => Array.isArray(d) ? d : (d?.suggestions || []);
  return (
    <Panel title="Suggested medication" icon={Sparkles} hint="LLM decision support">
      <Body state={state} isEmpty={(d) => norm(d).length === 0}
        empty={<EmptyState icon={Sparkles} text="No suggestions generated" />}>
        {(d) => (
          <div style={{ display: "grid", gap: 10 }}>
            {norm(d).map((s, i) => (
              <div key={i} style={{ background: T.tealSoft, borderRadius: 10, padding: "10px 12px" }}>
                <p style={{ margin: 0, fontFamily: body, fontSize: 13, fontWeight: 500, color: T.tealDeep }}>{s.drug || s.name}</p>
                {s.rationale && <p style={{ margin: "3px 0 0", fontFamily: body, fontSize: 12, color: T.sub }}>{s.rationale}</p>}
              </div>
            ))}
          </div>
        )}
      </Body>
    </Panel>
  );
}

function HistoryPanel({ state }) {
  const cols = [
    ["Start", "start_time"], ["Stop", "stop_time"], ["Route", "route"], ["Type", "drug_type"],
    ["Drug", "drug"], ["Strength", "product_strength"], ["Dose", "dose_value"],
    ["Unit", "dose_unit"], ["Form", "form_unit"], ["/24h", "doses_24h"],
  ];
  return (
    <Panel title="Complete drug history" icon={Layers} style={{ gridColumn: "1 / -1" }}>
      <Body state={state} skeletonH={140}
        empty={<EmptyState icon={Layers} text="No prescription history" />}>
        {(d) => (
          <div style={{ maxHeight: 300, overflow: "auto", border: `1px solid ${T.line}`, borderRadius: 10 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: mono, fontSize: 12 }}>
              <thead style={{ position: "sticky", top: 0, background: T.panel }}>
                <tr>{cols.map(([h]) => (
                  <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontFamily: body, fontSize: 10.5,
                    fontWeight: 600, color: T.sub, textTransform: "uppercase", letterSpacing: "0.04em",
                    borderBottom: `1px solid ${T.line}`, whiteSpace: "nowrap" }}>{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {d.map((row, i) => (
                  <tr key={i}>
                    {cols.map(([, k]) => (
                      <td key={k} style={{ padding: "9px 12px", borderBottom: `1px solid ${T.line}`,
                        whiteSpace: "nowrap", color: k === "drug" ? T.ink : T.sub }}>{row[k] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Body>
    </Panel>
  );
}

function ExplanationPanel({ state }) {
  const text = (d) => typeof d === "string" ? d : (d?.text || d?.summary || "");
  return (
    <Panel title="Prediction explanation" icon={FileText} style={{ gridColumn: "1 / -1" }}>
      <Body state={state} isEmpty={(d) => !text(d)}
        empty={<EmptyState icon={FileText} text="No explanation provided" />}>
        {(d) => (
          <p style={{ margin: 0, fontFamily: body, fontSize: 13.5, lineHeight: 1.65, color: T.ink }}>{text(d)}</p>
        )}
      </Body>
      <p style={{ margin: "14px 0 0", fontFamily: body, fontSize: 11.5, color: T.faint, borderTop: `1px solid ${T.line}`, paddingTop: 10 }}>
        Decision support only. The prescriber remains responsible for the clinical decision.
      </p>
    </Panel>
  );
}

/* ==================================================================
 *  Dashboard
 * ================================================================== */
export default function PatientInformation_dashboard({ apiBase = "/api", patientId = "10040025" }) {
  const ep = useMemo(() => buildEndpoints(apiBase, patientId), [apiBase, patientId]);
  const personal     = useJson(ep.personal);
  const trajectory   = useJson(ep.trajectory);
  const renalDrugs   = useJson(ep.renalDrugs);
  const drugHistory  = useJson(ep.drugHistory);
  const suggested    = useJson(ep.suggested);
  const risk         = useJson(ep.risk);
  const alerts       = useJson(ep.alerts);
  const interactions = useJson(ep.interactions);
  const explanation  = useJson(ep.explanation);

  return (
    <div style={{ background: T.bg, minHeight: "100%", padding: "clamp(16px,3vw,28px)", fontFamily: body }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.45; } }
        .pulse { animation: pulse 1.3s ease-in-out infinite; }
        button:focus-visible { outline: 2px solid ${T.tealDeep}; outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) { .pulse { animation: none; } }
        .bento { display: grid; gap: 14px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
        @media (max-width: 860px) { .bento { grid-template-columns: 1fr; } .bento > section { grid-column: auto !important; } }
      `}</style>

      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gap: 14 }}>
        <Banner personal={personal} risk={risk} patientId={patientId} />
        <KpiRow traj={trajectory} renalDrugs={renalDrugs} alerts={alerts} />

        <div className="bento">
          <TrendPanel state={trajectory} />
          <RiskPanel state={risk} />
          <RenalDrugsPanel state={renalDrugs} />
          <AlertsPanel state={alerts} />
          <InteractionsPanel state={interactions} />
          <SuggestedPanel state={suggested} />
          <HistoryPanel state={drugHistory} />
          <ExplanationPanel state={explanation} />
        </div>
      </div>
    </div>
  );
}
