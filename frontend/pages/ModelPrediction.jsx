import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  Activity, Gauge, Crosshair, ShieldCheck, AlertTriangle, Pill,
  Target, TrendingUp, Layers, FlaskConical, ScatterChart, CircleCheck,
  RefreshCw, LoaderCircle,
} from "lucide-react";

/* ------------------------------------------------------------------ *
 *  Design tokens — clinical instrument palette
 * ------------------------------------------------------------------ */
const T = {
  bg: "#E7EDEB", panel: "#FFFFFF", ink: "#0E2A2C", sub: "#5C7477", faint: "#93A9AA",
  line: "#DBE5E3", teal: "#0F766E", tealDeep: "#0A544D", tealSoft: "#D2E8E4",
  amber: "#D69A2D", coral: "#CD5540", coralSoft: "#F3DAD3", green: "#3E8E5B",
};
const display = "'Space Grotesk', system-ui, sans-serif";
const body = "'Inter', system-ui, sans-serif";
const mono = "'IBM Plex Mono', ui-monospace, monospace";

const pct = (x) => (x * 100).toFixed(1) + "%";
const dec = (x) => x.toFixed(3);

/* ------------------------------------------------------------------ *
 *  Normalise the raw JSON into what the UI consumes.
 *  Everything below is derived — nothing is hardcoded.
 * ------------------------------------------------------------------ */
function prettyFeature(f) {
  if (f.startsWith("drug_class_")) return "Drug class · " + f.replace("drug_class_", "");
  const map = {
    egfr: "eGFR", crcl: "Creatinine clearance", drug_protein_binding: "Drug protein binding",
    drug_pct_excreted: "% renally excreted", n_existing_drugs: "Existing drug count",
    drug_half_life: "Drug half-life", weight_kg: "Weight (kg)", age: "Age", sex: "Sex",
  };
  if (map[f]) return map[f];
  return f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function derive(raw) {
  if (!raw || !Array.isArray(raw.models)) throw new Error("missing a `models` array");
  const models = raw.models.map((m) => ({
    model: m.model, accuracy: m.accuracy, precision: m.precision, recall: m.recall,
    f1: m.f1, roc_auc: m.roc_auc, pr_auc: m.pr_auc,
    p_at_1: m.precision_at_1, p_at_3: m.precision_at_3,
  }));
  const best = models.find((m) => m.model === raw.best_model) || models[0];

  const c = raw.confusion_best || [[0, 0], [0, 0]];
  const cm = { tn: c[0][0], fp: c[0][1], fn: c[1][0], tp: c[1][1] };

  const r = (raw.curves_best && raw.curves_best.roc) || { fpr: [], tpr: [] };
  const roc = r.fpr.map((f, i) => ({ fpr: f, tpr: r.tpr[i], diag: f }));

  const feats = [...(raw.feature_importance || [])]
    .sort((a, b) => b.importance - a.importance)
    .map((x) => ({ f: x.feature, label: prettyFeature(x.feature), v: x.importance }));

  return {
    meta: { source: raw.source, n_patients: raw.n_patients, n_prescriptions: raw.n_prescriptions, best: best.model },
    best, models, cm, roc, feats,
  };
}

/* ------------------------------------------------------------------ *
 *  Small building blocks
 * ------------------------------------------------------------------ */
function Panel({ children, style, title, icon: Icon, hint }) {
  return (
    <section style={{
      background: T.panel, borderRadius: 14, border: `1px solid ${T.line}`,
      boxShadow: "0 1px 2px rgba(14,42,44,0.04)", padding: 20, ...style,
    }}>
      {title && (
        <header style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
          {Icon && (
            <span style={{ display: "grid", placeItems: "center", width: 30, height: 30,
              borderRadius: 8, background: T.tealSoft, color: T.tealDeep }}>
              <Icon size={16} strokeWidth={2.2} />
            </span>
          )}
          <div>
            <h2 style={{ margin: 0, fontFamily: display, fontSize: 15, fontWeight: 600,
              letterSpacing: "-0.01em", color: T.ink }}>{title}</h2>
            {hint && <p style={{ margin: "2px 0 0", fontFamily: body, fontSize: 11.5, color: T.faint }}>{hint}</p>}
          </div>
        </header>
      )}
      {children}
    </section>
  );
}

function Kpi({ label, value, sub, icon: Icon, tone = T.teal }) {
  return (
    <div style={{
      background: T.panel, border: `1px solid ${T.line}`, borderRadius: 12,
      padding: "16px 16px 14px", position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: tone }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontFamily: body, fontSize: 11, textTransform: "uppercase",
          letterSpacing: "0.06em", color: T.sub, fontWeight: 600 }}>{label}</span>
        {Icon && <Icon size={15} color={tone} strokeWidth={2.2} />}
      </div>
      <div style={{ fontFamily: mono, fontSize: 27, fontWeight: 500, color: T.ink, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontFamily: body, fontSize: 11.5, color: T.faint, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function Chip({ children, icon: Icon }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6,
      fontFamily: mono, fontSize: 12, color: T.sub, background: T.panel,
      border: `1px solid ${T.line}`, padding: "5px 10px", borderRadius: 999 }}>
      {Icon && <Icon size={13} color={T.teal} />} {children}
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

/* ------------------------------------------------------------------ *
 *  Charts / panels — all take props derived from the JSON
 * ------------------------------------------------------------------ */
function RocCurve({ roc }) {
  return (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={roc} margin={{ top: 6, right: 10, bottom: 4, left: -14 }}>
        <defs>
          <linearGradient id="rocFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={T.teal} stopOpacity={0.28} />
            <stop offset="100%" stopColor={T.teal} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={T.line} strokeDasharray="2 4" />
        <XAxis dataKey="fpr" type="number" domain={[0, 1]} tickCount={6}
          tick={{ fontFamily: mono, fontSize: 10, fill: T.faint }}
          label={{ value: "False positive rate", position: "insideBottom", offset: -2,
            style: { fontFamily: body, fontSize: 11, fill: T.sub } }} />
        <YAxis domain={[0, 1]} tickCount={6} tick={{ fontFamily: mono, fontSize: 10, fill: T.faint }} />
        <Tooltip content={({ active, payload }) => active && payload?.length
          ? <TT rows={[["FPR", payload[0].payload.fpr.toFixed(3)], ["TPR", payload[0].payload.tpr.toFixed(3)]]} /> : null} />
        <Area type="monotone" dataKey="diag" stroke={T.faint} strokeDasharray="4 4"
          strokeWidth={1} fill="none" dot={false} isAnimationActive={false} />
        <Area type="monotone" dataKey="tpr" stroke={T.teal} strokeWidth={2.4}
          fill="url(#rocFill)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

const axisLbl = { fontFamily: body, fontSize: 10.5, color: T.faint, textTransform: "uppercase", letterSpacing: "0.04em", textAlign: "center", alignSelf: "end", paddingBottom: 4 };

function Confusion({ cm }) {
  const total = cm.tn + cm.fp + cm.fn + cm.tp;
  const safe = (num, den) => (den ? num / den : 0);
  const cells = [
    { k: "TN", n: cm.tn, r: 0, c: 0, tone: T.tealDeep, bg: T.tealSoft, note: "Correctly cleared" },
    { k: "FP", n: cm.fp, r: 0, c: 1, tone: T.amber, bg: "#F7ECD3", note: "Over-flagged" },
    { k: "FN", n: cm.fn, r: 1, c: 0, tone: T.coral, bg: T.coralSoft, note: "Missed high-risk", danger: true },
    { k: "TP", n: cm.tp, r: 1, c: 1, tone: T.green, bg: "#DCEEE1", note: "Correctly flagged" },
  ];
  const derived = [
    ["Sensitivity", safe(cm.tp, cm.tp + cm.fn)],
    ["Specificity", safe(cm.tn, cm.tn + cm.fp)],
    ["PPV (precision)", safe(cm.tp, cm.tp + cm.fp)],
    ["NPV", safe(cm.tn, cm.tn + cm.fn)],
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)", gap: 20, alignItems: "start" }}>
      <div>
        <div style={{ display: "grid", gridTemplateColumns: "auto 1fr 1fr", gridTemplateRows: "auto 1fr 1fr", gap: 6 }}>
          <div />
          <div style={axisLbl}>Pred. low-risk</div>
          <div style={axisLbl}>Pred. high-risk</div>
          {["Actual low-risk", "Actual high-risk"].map((rowLbl, ri) => (
            <React.Fragment key={ri}>
              <div style={{ ...axisLbl, writingMode: "vertical-rl", transform: "rotate(180deg)", alignSelf: "stretch", display: "grid", placeItems: "center" }}>{rowLbl}</div>
              {cells.filter((c) => c.r === ri).sort((a, b) => a.c - b.c).map((c) => (
                <div key={c.k} style={{
                  background: c.bg, borderRadius: 10, padding: "14px 12px", minHeight: 88,
                  border: c.danger ? `1.5px solid ${T.coral}` : `1px solid ${T.line}`, position: "relative",
                }}>
                  <div style={{ fontFamily: mono, fontSize: 11, color: c.tone, fontWeight: 600 }}>{c.k}</div>
                  <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 500, color: T.ink, lineHeight: 1.1 }}>{c.n}</div>
                  <div style={{ fontFamily: body, fontSize: 10.5, color: T.sub, marginTop: 2 }}>{c.note}</div>
                  {c.danger && <AlertTriangle size={14} color={T.coral} style={{ position: "absolute", top: 12, right: 12 }} />}
                </div>
              ))}
            </React.Fragment>
          ))}
        </div>
        <p style={{ fontFamily: body, fontSize: 11, color: T.faint, margin: "12px 2px 0" }}>
          {total} held-out prescriptions. The {cm.fn} false negatives are the clinically costly errors — high-risk prescriptions the model let through.
        </p>
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {derived.map(([lbl, v]) => (
          <div key={lbl} style={{ display: "grid", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: body, fontSize: 12, color: T.sub }}>
              <span>{lbl}</span><span style={{ fontFamily: mono, color: T.ink }}>{pct(v)}</span>
            </div>
            <div style={{ height: 6, background: T.line, borderRadius: 999 }}>
              <div style={{ width: pct(v), height: "100%", background: T.teal, borderRadius: 999 }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const METRICS = [
  { key: "roc_auc", label: "ROC-AUC" }, { key: "pr_auc", label: "PR-AUC" },
  { key: "accuracy", label: "Accuracy" }, { key: "f1", label: "F1" },
  { key: "precision", label: "Precision" }, { key: "recall", label: "Recall" },
];

function Comparison({ models, best }) {
  const [metric, setMetric] = useState("roc_auc");
  const data = useMemo(
    () => [...models].sort((a, b) => b[metric] - a[metric])
      .map((m) => ({ name: m.model, v: m[metric], best: m.model === best })),
    [metric, models, best]
  );
  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
        {METRICS.map((m) => {
          const on = m.key === metric;
          return (
            <button key={m.key} onClick={() => setMetric(m.key)} style={{
              fontFamily: body, fontSize: 12, fontWeight: 500, cursor: "pointer",
              padding: "6px 12px", borderRadius: 999,
              border: `1px solid ${on ? T.teal : T.line}`,
              background: on ? T.teal : T.panel, color: on ? "#fff" : T.sub,
            }}>{m.label}</button>
          );
        })}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 4, right: 12, bottom: 44, left: -14 }}>
          <CartesianGrid stroke={T.line} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="name" interval={0} angle={-32} textAnchor="end" height={70}
            tick={{ fontFamily: body, fontSize: 10.5, fill: T.sub }} />
          <YAxis domain={[0, 1]} tick={{ fontFamily: mono, fontSize: 10, fill: T.faint }} />
          <Tooltip cursor={{ fill: "rgba(15,118,110,0.06)" }}
            content={({ active, payload }) => active && payload?.length
              ? <TT rows={[[payload[0].payload.name, dec(payload[0].value)]]} /> : null} />
          <Bar dataKey="v" radius={[5, 5, 0, 0]} maxBarSize={54}>
            {data.map((d, i) => <Cell key={i} fill={d.best ? T.teal : "#B7CDCA"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

function Importance({ feats }) {
  const max = feats.length ? feats[0].v : 1;
  return (
    <ResponsiveContainer width="100%" height={Math.max(240, feats.length * 28)}>
      <BarChart layout="vertical" data={feats} margin={{ top: 0, right: 40, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={T.line} strokeDasharray="2 4" horizontal={false} />
        <XAxis type="number" domain={[0, Math.ceil(max * 100) / 100]} tick={{ fontFamily: mono, fontSize: 10, fill: T.faint }} />
        <YAxis type="category" dataKey="label" width={140} tick={{ fontFamily: body, fontSize: 11, fill: T.ink }} />
        <Tooltip cursor={{ fill: "rgba(15,118,110,0.06)" }}
          content={({ active, payload }) => active && payload?.length
            ? <TT rows={[[payload[0].payload.label, pct(payload[0].value)]]} /> : null} />
        <Bar dataKey="v" radius={[0, 5, 5, 0]} maxBarSize={20}>
          {feats.map((d, i) => {
            const t = 0.35 + 0.65 * (d.v / max);
            return <Cell key={i} fill={`rgba(15,118,110,${t.toFixed(2)})`} />;
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function Leaderboard({ models, best }) {
  const cols = [
    ["Model", "model"], ["Acc", "accuracy"], ["Prec", "precision"], ["Rec", "recall"],
    ["F1", "f1"], ["ROC-AUC", "roc_auc"], ["PR-AUC", "pr_auc"], ["P@1", "p_at_1"], ["P@3", "p_at_3"],
  ];
  const rows = [...models].sort((a, b) => b.roc_auc - a.roc_auc);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: mono, fontSize: 12.5 }}>
        <thead>
          <tr>{cols.map(([h], i) => (
            <th key={h} style={{ textAlign: i === 0 ? "left" : "right", padding: "0 12px 10px",
              fontFamily: body, fontSize: 11, fontWeight: 600, color: T.sub,
              textTransform: "uppercase", letterSpacing: "0.04em",
              borderBottom: `1px solid ${T.line}`, whiteSpace: "nowrap" }}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {rows.map((m) => {
            const isBest = m.model === best;
            return (
              <tr key={m.model} style={{ background: isBest ? T.tealSoft : "transparent" }}>
                {cols.map(([, key], ci) => (
                  <td key={key} style={{
                    padding: "11px 12px", textAlign: ci === 0 ? "left" : "right",
                    borderBottom: `1px solid ${T.line}`, whiteSpace: "nowrap",
                    color: ci === 0 ? T.ink : T.sub,
                    fontWeight: ci === 0 && isBest ? 600 : 400, fontFamily: ci === 0 ? body : mono,
                  }}>
                    {ci === 0
                      ? <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                          {isBest && <CircleCheck size={14} color={T.teal} />}{m.model}
                        </span>
                      : (m[key] ?? 0).toFixed(3)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 *  The dashboard — pure view over derived data
 * ------------------------------------------------------------------ */
function Dashboard({ d }) {
  const b = d.best;
  const kpis = [
    { label: "ROC-AUC", value: dec(b.roc_auc), sub: "Discrimination", icon: Activity, tone: T.teal },
    { label: "PR-AUC", value: dec(b.pr_auc), sub: "Precision–recall", icon: TrendingUp, tone: T.teal },
    { label: "Accuracy", value: pct(b.accuracy), sub: "Overall correct", icon: Target, tone: T.tealDeep },
    { label: "Precision", value: pct(b.precision), sub: "Of flagged, correct", icon: Crosshair, tone: T.green },
    { label: "Recall", value: pct(b.recall), sub: "Of risky, caught", icon: ShieldCheck, tone: T.amber },
    { label: "F1", value: dec(b.f1), sub: "Balanced score", icon: Gauge, tone: T.tealDeep },
  ];
  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gap: 18 }}>
      <header className="rise" style={{ display: "flex", flexWrap: "wrap", gap: 16,
        justifyContent: "space-between", alignItems: "flex-end" }}>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <span style={{ display: "grid", placeItems: "center", width: 46, height: 46,
            borderRadius: 12, background: T.teal, color: "#fff" }}>
            <Pill size={22} strokeWidth={2.2} />
          </span>
          <div>
            <h1 style={{ margin: 0, fontFamily: display, fontSize: "clamp(20px,3vw,26px)",
              fontWeight: 700, letterSpacing: "-0.02em", color: T.ink }}>
              Medication-Risk Model — Evaluation
            </h1>
            <p style={{ margin: "3px 0 0", fontFamily: body, fontSize: 13, color: T.sub }}>
              Renal dose-adjustment risk prediction · held-out test performance
            </p>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          {d.meta.source && <Chip icon={FlaskConical}>{String(d.meta.source).toUpperCase()}</Chip>}
          {d.meta.n_patients != null && <Chip icon={Layers}>{d.meta.n_patients} patients</Chip>}
          {d.meta.n_prescriptions != null && <Chip>{d.meta.n_prescriptions} prescriptions</Chip>}
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6,
            fontFamily: body, fontSize: 12, fontWeight: 600, color: "#fff",
            background: T.tealDeep, padding: "6px 12px", borderRadius: 999 }}>
            <CircleCheck size={14} /> Best · {d.meta.best}
          </span>
        </div>
      </header>

      <div className="rise" style={{ display: "grid", gap: 12,
        gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
        {kpis.map((k) => <Kpi key={k.label} {...k} />)}
      </div>

      <div className="rise" style={{ display: "grid", gap: 18,
        gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))" }}>
        <Panel title="ROC curve" icon={ScatterChart}
          hint={`${d.meta.best} · AUC ${dec(b.roc_auc)} vs. 0.500 chance line`}>
          <RocCurve roc={d.roc} />
        </Panel>
        <Panel title="Confusion matrix" icon={AlertTriangle}
          hint="Best model at its operating threshold">
          <Confusion cm={d.cm} />
        </Panel>
      </div>

      <Panel className="rise" title="Model comparison" icon={Gauge}
        hint="Ranked by the selected metric across all candidates">
        <Comparison models={d.models} best={d.meta.best} />
      </Panel>

      <div className="rise" style={{ display: "grid", gap: 18,
        gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))" }}>
        <Panel title="Feature importance" icon={TrendingUp}
          hint={`${d.meta.best} · contribution to predictions`}>
          <Importance feats={d.feats} />
        </Panel>
        <Panel title="Leaderboard" icon={Layers} hint="All models, sorted by ROC-AUC">
          <Leaderboard models={d.models} best={d.meta.best} />
        </Panel>
      </div>

      <footer style={{ fontFamily: body, fontSize: 11.5, color: T.faint, textAlign: "center", paddingTop: 4 }}>
        Rendered at runtime from the metrics file — no values hardcoded.
      </footer>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 *  Centered status screens (loading / error)
 * ------------------------------------------------------------------ */
function Splash({ children }) {
  return (
    <div style={{ maxWidth: 520, margin: "12vh auto 0", textAlign: "center" }}>
      <span style={{ display: "grid", placeItems: "center", width: 52, height: 52, margin: "0 auto 18px",
        borderRadius: 14, background: T.teal, color: "#fff" }}>
        <Pill size={26} strokeWidth={2.2} />
      </span>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 *  Entry — fetches /model_metrics.json from the public folder.
 *  Pass a `src` to change the path, or `data` to skip the fetch.
 * ------------------------------------------------------------------ */
export default function ModelDashboard({ src = "/model_metrics.json", data }) {
  const [raw, setRaw] = useState(data ?? null);
  const [status, setStatus] = useState(data ? "ready" : "loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [nonce, setNonce] = useState(0); // bump to retry

  const load = useCallback(() => {
    setStatus("loading");
    setError(null);
    fetch(src)
      .then(async (r) => {
        console.log("Status:", r.status);
        const text = await r.text();
        console.log(text); // See what's actually returned
        if (!r.ok) throw new Error(`HTTP ${r.status} for ${src}`);
        return JSON.parse(text);
      })
      .then((parsed) => {
        derive(parsed); // validate shape before committing
        setRaw(parsed);
        setStatus("ready");
      })
      .catch((e) => {
        console.error("Failed to load metrics:", e);
        setError(e.message || String(e));
        setStatus("error");
      });
  }, [src]);

  useEffect(() => {
    if (data) return; // data prop wins — no fetch
    load();
  }, [data, load, nonce]);

  const derived = useMemo(() => {
    if (!raw) return null;
    try { return derive(raw); } catch { return null; }
  }, [raw]);

  return (
    <div style={{ background: T.bg, minHeight: "100%", padding: "clamp(16px,3vw,32px)", fontFamily: body }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
        @keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
        @keyframes spin { to { transform: rotate(360deg); } }
        .rise { animation: rise .5s cubic-bezier(.2,.7,.3,1) both; }
        .spin { animation: spin 1s linear infinite; }
        button:focus-visible { outline: 2px solid ${T.tealDeep}; outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) { .rise, .spin { animation: none; } }
      `}</style>

      {status === "ready" && derived && <Dashboard d={derived} />}

      {status === "loading" && (
        <Splash>
          <LoaderCircle className="spin" size={26} color={T.teal} />
          <p style={{ margin: "14px 0 0", fontFamily: body, fontSize: 14, color: T.sub }}>
            Loading model metrics…
          </p>
          <p style={{ margin: "4px 0 0", fontFamily: mono, fontSize: 11.5, color: T.faint }}>{src}</p>
        </Splash>
      )}

      {status === "error" && (
        <Splash>
          <h1 style={{ margin: 0, fontFamily: display, fontSize: 20, fontWeight: 700, color: T.ink }}>
            Couldn’t load the metrics
          </h1>
          <div style={{ margin: "14px auto 0", display: "inline-flex", alignItems: "flex-start", gap: 8,
            fontFamily: body, fontSize: 12.5, color: T.coral, background: T.coralSoft, textAlign: "left",
            border: `1px solid ${T.coral}`, padding: "10px 12px", borderRadius: 10, maxWidth: 460 }}>
            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>{error}. Confirm <code style={{ fontFamily: mono }}>model_metrics.json</code> is in <code style={{ fontFamily: mono }}>public/</code> and served at <code style={{ fontFamily: mono }}>{src}</code>.</span>
          </div>
          <div>
            <button onClick={() => setNonce((n) => n + 1)} style={{
              marginTop: 18, display: "inline-flex", alignItems: "center", gap: 7, cursor: "pointer",
              fontFamily: body, fontSize: 13, fontWeight: 500, color: "#fff",
              background: T.teal, border: "none", padding: "8px 16px", borderRadius: 999 }}>
              <RefreshCw size={14} /> Retry
            </button>
          </div>
        </Splash>
      )}
    </div>
  );
}
