import React, { useEffect, useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'

const TEAL = '#0b6b5b', AMBER = '#b26a00', RED = '#a3231f', MUT = '#5c6b68'
const SET_COLOR = { 'A. renal only': '#94a3b8', 'B. renal + K+': '#2a78d6', 'C. full (+drugs)': TEAL }

function Kpi({ label, value }) {
  return <div className="kpi"><div className="kpi-label">{label}</div><div className="kpi-value">{value}</div></div>
}

export default function PotassiumModelDashboard() {
  const [m, setM] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    fetch('/potassium_metrics.json')
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json() })
      .then(setM).catch((e) => setErr(String(e)))
  }, [])

  if (err) return <div className="empty">Could not load potassium_metrics.json ({err}). Run potassium_model.py --metrics-json.</div>
  if (!m) return <div className="empty">Loading potassium model metrics…</div>

  const f3 = (v) => (v == null ? '—' : v.toFixed(3))
  const pct = (v) => (v * 100).toFixed(1) + '%'

  const modelNames = [...new Set(m.results.map((r) => r.model))]
  const grid = modelNames.map((model) => {
    const row = { model }
    m.results.filter((r) => r.model === model).forEach((r) => { row[r.features] = r.roc_auc })
    return row
  }).sort((a, b) => (b['C. full (+drugs)'] || 0) - (a['C. full (+drugs)'] || 0))

  const roc = m.curves_best.roc.fpr.map((f, i) => ({ fpr: f, tpr: m.curves_best.roc.tpr[i] }))
  const pr = m.curves_best.pr.recall.map((r, i) => ({ recall: r, precision: m.curves_best.pr.precision[i] }))
  const cm = m.confusion_best
  const imp = m.feature_importance

  return (
    <div className="dash">
      <div className="dash-head">
        <h2>Potassium risk model</h2>
        <span className="dash-sub">{m.n_patients} patients · breach rate {pct(m.breach_rate)}</span>
      </div>

      <div className="kpi-row">
        <Kpi label="Best model" value={m.best.model} />
        <Kpi label="Best ROC-AUC" value={f3(m.best.roc_auc)} />
        <Kpi label="Renal-only AUC" value={f3(m.ablation.renal_only_auc)} />
        <Kpi label="Gain from K+/drugs" value={'+' + f3(m.ablation.gain)} />
      </div>

      <div className="panel">
        <h3>Ablation — does drug burden add signal beyond renal function?</h3>
        <p style={{ fontSize: 13, color: MUT, margin: '0 0 12px' }}>
          Three feature sets compared, every model: <strong>A</strong> renal only (eGFR,
          creatinine, CKD stage, age) · <strong>B</strong> adds the patient's own potassium
          history · <strong>C</strong> adds potassium-affecting drug burden.
        </p>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={grid} margin={{ top: 5, right: 12, bottom: 40, left: -10 }}>
            <CartesianGrid stroke="#eef3f1" vertical={false} />
            <XAxis dataKey="model" tick={{ fontSize: 10, fill: MUT }} angle={-30} textAnchor="end" interval={0} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: MUT }} />
            <Tooltip formatter={(v) => f3(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine y={0.5} stroke={RED} strokeDasharray="4 4" />
            <Bar dataKey="A. renal only" fill={SET_COLOR['A. renal only']} radius={[3, 3, 0, 0]} />
            <Bar dataKey="B. renal + K+" fill={SET_COLOR['B. renal + K+']} radius={[3, 3, 0, 0]} />
            <Bar dataKey="C. full (+drugs)" fill={SET_COLOR['C. full (+drugs)']} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="fc-foot">
          Renal-only best AUC {f3(m.ablation.renal_only_auc)} → full-model best AUC{' '}
          {f3(m.ablation.full_auc)} (gain +{f3(m.ablation.gain)}).{' '}
          {m.ablation.gain >= 0.02
            ? 'Drug burden and potassium history add signal beyond kidney function alone.'
            : 'Drug features add little beyond renal function — reported as a genuine finding.'}
        </div>
      </div>

      <div className="panel-row">
        <div className="panel">
          <h3>ROC curve — {m.best.model} ({m.best.features})</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart margin={{ top: 5, right: 12, bottom: 5, left: -12 }}>
              <CartesianGrid stroke="#eef3f1" />
              <XAxis type="number" dataKey="fpr" domain={[0, 1]} data={roc} tick={{ fontSize: 10, fill: MUT }} />
              <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 10, fill: MUT }} />
              <Tooltip formatter={(v) => f3(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Line data={roc} dataKey="tpr" stroke={TEAL} strokeWidth={2.5} dot={false} />
              <Line data={[{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }]} dataKey="tpr" stroke="#94a3b8" strokeDasharray="5 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Precision-recall — {m.best.model}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={pr} margin={{ top: 5, right: 12, bottom: 5, left: -12 }}>
              <CartesianGrid stroke="#eef3f1" />
              <XAxis type="number" dataKey="recall" domain={[0, 1]} tick={{ fontSize: 10, fill: MUT }} />
              <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 10, fill: MUT }} />
              <Tooltip formatter={(v) => f3(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Line dataKey="precision" stroke={AMBER} strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {imp.length > 0 && (
        <div className="panel">
          <h3>Feature importance — {m.best.model}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={imp} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 90 }}>
              <CartesianGrid stroke="#eef3f1" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10, fill: MUT }} />
              <YAxis type="category" dataKey="feature" tick={{ fontSize: 11, fill: '#0f2e2a' }} width={110} />
              <Tooltip formatter={(v) => v.toFixed(3)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="importance" fill={TEAL} radius={[0, 4, 4, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="panel-row">
        <div className="panel">
          <h3>Confusion matrix — {m.best.model}</h3>
          <div className="cm">
            <div className="cm-corner" /><div className="cm-head">Pred: no breach</div><div className="cm-head">Pred: breach</div>
            <div className="cm-head side">True: no breach</div>
            <div className="cm-cell tn">{cm[0][0]}</div><div className="cm-cell fp">{cm[0][1]}</div>
            <div className="cm-head side">True: breach</div>
            <div className="cm-cell fn">{cm[1][0]}</div><div className="cm-cell tp">{cm[1][1]}</div>
          </div>
        </div>
        <div className="panel">
          <h3>All models × feature sets</h3>
          <table className="metrics-table">
            <thead><tr><th>model</th><th>features</th><th>AUC</th><th>F1</th></tr></thead>
            <tbody>
              {m.results.filter(r => r.roc_auc != null).sort((a,b)=>b.roc_auc-a.roc_auc).map((r, i) => (
                <tr key={i} className={r.model === m.best.model && r.features === m.best.features ? 'best' : ''}>
                  <td>{r.model}</td><td style={{ fontSize: 11 }}>{r.features}</td>
                  <td>{f3(r.roc_auc)}</td><td>{f3(r.f1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
