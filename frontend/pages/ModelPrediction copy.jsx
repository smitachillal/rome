// export default function ModelPrediction() {
//   return (
//     <div className="empty">
//       <h2>Model prediction</h2>
//       <p>Nothing here yet. Add model metrics, cohort-level predictions and threshold controls to this page.</p>
//     </div>
//   )
// }
import React, { useEffect, useState } from 'react'

import {
  FaBrain,
  FaDatabase,
  FaUsers,
  FaPrescriptionBottleAlt,
  FaBullseye,
  FaChartLine,
  FaAward,
} from "react-icons/fa";

import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine, LabelList
} from 'recharts'

import {
  FaChartBar,
  FaTrophy,
} from "react-icons/fa";
// import {
//   LabelList,
//   BarChart,
//   Bar,
//   Tooltip,
//   XAxis,
//   YAxis,
//   Cell,
//   ReferenceLine,
// } from "recharts";

const TEAL = '#0b6b5b', AMBER = '#b26a00', RED = '#a3231f', GREY = '#7c9c95', MUT = '#5c6b68'

// colour a model bar by tier (ensemble = teal, weak = amber, failing = red)
function barColor(auc) {
  if (auc >= 0.8) return TEAL
  if (auc >= 0.6) return AMBER
  return RED
}

function Kpi({ label, value }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
    </div>
  )
}

export default function ModelPrediction() {
  const [m, setM] = useState(null)
  const [err, setErr] = useState(null)

useEffect(() => {
  fetch("/model_metrics.json")
    .then(async (r) => {
      console.log("Status:", r.status);

      const text = await r.text();
      console.log(text);   // See what's actually returned

      return JSON.parse(text);
    })
    .then(setM)
    .catch((e) => {
      console.error(e);
      setErr(String(e));
    });
}, []);

  if (err) return <div className="empty">Could not load model_metrics.json 1 ({err}). Run the model with --metrics-json.</div>
  if (!m) return <div className="empty">Loading model metrics…</div>

  const best = m.models.find((x) => x.model === m.best_model) || m.models[0]
  const comparison = [...m.models].sort((a, b) => b.roc_auc - a.roc_auc)
  const roc = m.curves_best.roc.fpr.map((f, i) => ({ fpr: f, tpr: m.curves_best.roc.tpr[i] }))
  const pr = m.curves_best.pr.recall.map((r, i) => ({ recall: r, precision: m.curves_best.pr.precision[i] }))
  const imp = m.feature_importance.slice(0, 10)
  const cm = m.confusion_best  // [[TN,FP],[FN,TP]]

  const pct = (v) => (v * 100).toFixed(1) + '%'
  const f3 = (v) => v.toFixed(3)

  return (
    <>
    <style>{`
      .dashboard-header {
        background: linear-gradient(135deg, #2563eb, #4f46e5);
        color: white;
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.12);
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 20px;
      }

      .header-icon {
        width: 70px;
        height: 70px;
        border-radius: 16px;
        background: rgba(255,255,255,.18);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 30px;
      }

      .dashboard-header h2 {
        margin: 0;
        font-size: 30px;
        font-weight: 700;
      }

      .header-subtitle {
        margin-top: 10px;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        color: rgba(255,255,255,.92);
        font-size: 15px;
      }

      .header-subtitle span {
        opacity: .5;
      }

      .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px,1fr));
        gap: 20px;
        margin-bottom: 28px;
      }

      .kpi-card {
        background: white;
        border-radius: 16px;
        padding: 22px;
        display: flex;
        align-items: center;
        gap: 18px;
        box-shadow: 0 8px 24px rgba(15,23,42,.08);
        transition: .25s ease;
        border: 1px solid #eef2f7;
      }

      .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 16px 35px rgba(15,23,42,.12);
      }

      .kpi-icon {
        width: 58px;
        height: 58px;
        border-radius: 14px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 24px;
      }

      .kpi-label {
        color: #64748b;
        font-size: 14px;
        margin-bottom: 6px;
      }

      .kpi-value {
        font-size: 24px;
        font-weight: 700;
        color: #0f172a;
      }

      .chart-panel {
    background: #fff;
    border-radius: 18px;
    padding: 22px;
    box-shadow: 0 8px 30px rgba(15,23,42,.08);
}

.panel-header{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:20px;
}

.panel-title{
    display:flex;
    align-items:center;
    gap:14px;
}

.panel-icon{
    width:46px;
    height:46px;
    border-radius:12px;
    padding:12px;
    background:#eff6ff;
    color:#2563eb;
}

.panel-title h3{
    margin:0;
    font-size:20px;
    color:#0f172a;
}

.panel-title span{
    color:#64748b;
    font-size:13px;
}

.best-model-badge{
    display:flex;
    align-items:center;
    gap:8px;
    background:#ecfdf5;
    color:#059669;
    padding:8px 14px;
    border-radius:30px;
    font-size:13px;
    font-weight:600;
    border:1px solid #bbf7d0;
}
    `}</style>

     
    


    


    <div className="dash">
      {/* <div className="dash-head">
        <h2>Model performance</h2>
        <span className="dash-sub">
          {m.source} data · {m.n_patients} patients · {m.n_prescriptions} prescriptions
        </span>
      </div>

      {/* KPI row * / }
      <div className="kpi-row">
        <Kpi label="Best model" value={m.best_model} />
        <Kpi label="ROC-AUC" value={f3(best.roc_auc)} />
        <Kpi label="Precision@1" value={f3(best.precision_at_1)} />
        <Kpi label="Accuracy" value={pct(best.accuracy)} />
      </div> */}


      <div className="dashboard-header">
        <div className="header-left">
          <div className="header-icon">
            <FaBrain />
          </div>

          <div>
            <h2>Model Performance Dashboard</h2>

            <p className="header-subtitle">
              <FaDatabase /> {m.source.toUpperCase()} Dataset
              <span>•</span>
              <FaUsers /> {m.n_patients} Patients
              <span>•</span>
              <FaPrescriptionBottleAlt /> {m.n_prescriptions} Prescriptions
            </p>
          </div>
        </div>
      </div>

      <div className="kpi-grid">
        <Kpi
          icon={<FaAward />}
          color="#8B5CF6"
          label="Best Model"
          value={m.best_model}
        />

        <Kpi
          icon={<FaChartLine />}
          color="#10B981"
          label="ROC-AUC"
          value={f3(best.roc_auc)}
        />

        <Kpi
          icon={<FaBullseye />}
          color="#F59E0B"
          label="Precision @1"
          value={f3(best.precision_at_1)}
        />

        <Kpi
          icon={<FaChartLine />}
          color="#3B82F6"
          label="Accuracy"
          value={pct(best.accuracy)}
        />
      </div>



      <div className="panel chart-panel">
  <div className="panel-header">
    <div className="panel-title">
      <FaChartBar className="panel-icon" />
      <div>
        <h3>Model Comparison</h3>
        <span>ROC-AUC on held-out patients</span>
      </div>
    </div>

    <div className="best-model-badge">
      <FaTrophy />
      {m.best_model}
    </div>
  </div>

  <ResponsiveContainer width="50%" height={330}>
    <BarChart
      data={comparison}
      margin={{ top: 20, right: 25, bottom: 55, left: 10 }}
    >
      <CartesianGrid
        vertical={false}
        strokeDasharray="3 3"
        stroke="#edf2f7"
      />

      <XAxis
        dataKey="model"
        interval={0}
        angle={-25}
        textAnchor="end"
        tick={{ fontSize: 17 }}
      />

      <YAxis
        domain={[0.4, 1]}
        tickFormatter={(v) => v.toFixed(1)}
      />

      <Tooltip
        formatter={(v) => [f3(v), "ROC-AUC"]}
        cursor={{ fill: "#f8fafc" }}
        contentStyle={{
          borderRadius: 12,
          border: "none",
          boxShadow: "0 8px 25px rgba(0,0,0,.12)",
        }}
      />

      <ReferenceLine
        y={0.5}
        stroke="#ef4444"
        strokeDasharray="5 5"
        label={{
          value: "Baseline",
          fill: "#ef4444",
          position: "insideTopRight",
        }}
      />

      <Bar
        dataKey="roc_auc"
        radius={[8, 8, 0, 0]}
      >
        {comparison.map((row, index) => (
          <Cell
            key={index}
            fill={
              row.model === m.best_model
                ? "#F59E0B"
                : "#3b82f6"
            }
          />
        ))}

        <LabelList
          dataKey="roc_auc"
          position="top"
          formatter={(v) => v.toFixed(3)}
          style={{
            fontSize: 11,
            fontWeight: 600,
          }}
        />
      </Bar>
    </BarChart>
  </ResponsiveContainer>
</div>


      {/* Model comparison */}

    {/* <div className="panel">
        <h3>Model comparison — ROC-AUC (held-out patients)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={comparison} margin={{ top: 5, right: 12, bottom: 40, left: -10 }}>
            <CartesianGrid stroke="#eef3f1" vertical={false} />
            <XAxis dataKey="model" tick={{ fontSize: 10, fill: MUT }} angle={-35} textAnchor="end" interval={0} />
            <YAxis domain={[0.4, 1]} tick={{ fontSize: 11, fill: MUT }} />
            <Tooltip formatter={(v) => f3(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <ReferenceLine y={0.5} stroke={RED} strokeDasharray="4 4" />
            <Bar dataKey="roc_auc" radius={[4, 4, 0, 0]}>
              {comparison.map((d, i) => <Cell key={i} fill={barColor(d.roc_auc)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div> */}

      {/* ROC + PR side by side */}
      {/* <div className="panel-row">
        <div className="panel">
          <h3>ROC curve — {m.best_model}</h3>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart margin={{ top: 5, right: 12, bottom: 5, left: -12 }}>
              <CartesianGrid stroke="#eef3f1" />
              <XAxis type="number" dataKey="fpr" domain={[0, 1]} data={roc}
                tick={{ fontSize: 10, fill: MUT }} label={{ value: 'FPR', position: 'insideBottom', offset: -2, fontSize: 10, fill: MUT }} />
              <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 10, fill: MUT }} />
              <Tooltip formatter={(v) => f3(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Line data={roc} dataKey="tpr" stroke={TEAL} strokeWidth={2.5} dot={false} />
              <Line data={[{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }]} dataKey="tpr" stroke={GREY} strokeWidth={1} strokeDasharray="5 4" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <h3>Precision-recall — {m.best_model}</h3>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={pr} margin={{ top: 5, right: 12, bottom: 5, left: -12 }}>
              <CartesianGrid stroke="#eef3f1" />
              <XAxis type="number" dataKey="recall" domain={[0, 1]} tick={{ fontSize: 10, fill: MUT }}
                label={{ value: 'recall', position: 'insideBottom', offset: -2, fontSize: 10, fill: MUT }} />
              <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 10, fill: MUT }} />
              <Tooltip formatter={(v) => f3(v)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Line dataKey="precision" stroke={AMBER} strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div> */}

      {/* Feature importance */}
      <div className="panel">
        <h3>Feature importance — what drives the prediction</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={imp} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 70 }}>
            <CartesianGrid stroke="#eef3f1" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: MUT }} />
            <YAxis type="category" dataKey="feature" tick={{ fontSize: 11, fill: '#0f2e2a' }} width={130} />
            <Tooltip formatter={(v) => v.toFixed(3)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Bar dataKey="importance" fill={TEAL} radius={[0, 4, 4, 0]} barSize={16} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Confusion matrix + full metrics table */}
      <div className="panel-row">
        <div className="panel">
          <h3>Confusion matrix — {m.best_model}</h3>
          <div className="cm">
            <div className="cm-corner" />
            <div className="cm-head">Pred: not</div>
            <div className="cm-head">Pred: presc.</div>
            <div className="cm-head side">True: not</div>
            <div className="cm-cell tn">{cm[0][0]}</div>
            <div className="cm-cell fp">{cm[0][1]}</div>
            <div className="cm-head side">True: presc.</div>
            <div className="cm-cell fn">{cm[1][0]}</div>
            <div className="cm-cell tp">{cm[1][1]}</div>
          </div>
        </div>
        <div className="panel">
          <h3>All metrics</h3>
          <table className="metrics-table">
            <thead><tr><th>model</th><th>AUC</th><th>F1</th><th>P@1</th></tr></thead>
            <tbody>
              {comparison.map((r) => (
                <tr key={r.model} className={r.model === m.best_model ? 'best' : ''}>
                  <td>{r.model}</td><td>{f3(r.roc_auc)}</td>
                  <td>{f3(r.f1)}</td><td>{f3(r.precision_at_1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    </>
  )
}