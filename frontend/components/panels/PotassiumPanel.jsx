import React, { useEffect, useState } from 'react'
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceArea,
} from 'recharts'
import { getPotassium , getPotassiumPrediction } from '../../api/client.js'




const BAND = {
  severe_hyperkalaemia: { cls: 'urgent', color: '#a3231f' },
  hyperkalaemia:        { cls: 'urgent', color: '#c2410c' },
  high_normal:          { cls: 'review', color: '#b26a00' },
  normal:               { cls: 'ok',     color: '#0b6b5b' },
  hypokalaemia:         { cls: 'urgent', color: '#c2410c' },
  severe_hypokalaemia:  { cls: 'urgent', color: '#a3231f' },
}

export default function PotassiumPanel({ patientId }) {
  const [k, setK] = useState(null)
  const [err, setErr] = useState(null)
  const [pred, setPred] = useState(null)
  useEffect(() => {
    if (patientId == null) return
    setK(null); setErr(null)
    console.log( ' In potassium ',patientId )
    getPotassium(patientId).then(setK).catch((e) => setErr(String(e)))
    console.log( ' In getPotassiumPrediction ',patientId )
    getPotassiumPrediction(patientId).then(setPred).catch(() => {})
  }, [patientId])



  if (err) return <div className="rec-empty">Could not load potassium ({err}).</div>
  if (!k) return <div className="rec-empty">Loading potassium…</div>
  if (!k.available) return (
    <div className="section"><h3>Potassium</h3>
      <div className="rec-empty">{k.reason}</div></div>
  )

  const band = BAND[k.flag] || BAND.normal
  const t = k.thresholds

  // const [pred, setPred] = useState(null)
  // useEffect(() => {
  //   if (patientId == null) return
  //   console.log( ' In getPotassiumPrediction ',patientId )
  //   getPotassiumPrediction(patientId).then(setPred).catch(() => {})
  // }, [patientId])


  return (
    <div className="section">
      <h3>Potassium — hyper / hypokalaemia risk</h3>

      {/* headline band */}
      <div className={'k-headline k-' + band.cls}>
        <span className="k-value">{k.latest.potassium}</span>
        <span className="k-unit">mmol/L</span>
        <span className={'chip ' + band.cls}>{k.label}</span>
        <span className="k-detail">{k.detail}</span>
      </div>

      {/* trajectory with threshold bands */}
      <ResponsiveContainer width="100%" height={230}>
        <ComposedChart data={k.trajectory} margin={{ top: 8, right: 14, bottom: 4, left: -12 }}>
          <CartesianGrid stroke="#eef3f1" vertical={false} />
          {/* danger zones */}
          <ReferenceArea y1={t.high} y2={8} fill="#a3231f" fillOpacity={0.07} />
          <ReferenceArea y1={2} y2={t.low} fill="#a3231f" fillOpacity={0.07} />
          <ReferenceArea y1={t.low} y2={t.high_normal} fill="#0b6b5b" fillOpacity={0.05} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#5c6b68' }} minTickGap={40} />
          <YAxis domain={[2.5, 7.5]} tick={{ fontSize: 11, fill: '#5c6b68' }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <ReferenceLine y={t.severe_high} stroke="#a3231f" strokeDasharray="4 4"
            label={{ value: '6.0 urgent', fontSize: 9, fill: '#a3231f', position: 'insideTopRight' }} />
          <ReferenceLine y={t.high} stroke="#c2410c" strokeDasharray="4 4"
            label={{ value: '5.5', fontSize: 9, fill: '#c2410c', position: 'insideTopRight' }} />
          <ReferenceLine y={t.low} stroke="#c2410c" strokeDasharray="4 4"
            label={{ value: '3.5', fontSize: 9, fill: '#c2410c', position: 'insideBottomRight' }} />
          <ReferenceLine y={t.severe_low} stroke="#a3231f" strokeDasharray="4 4"
            label={{ value: '3.0 urgent', fontSize: 9, fill: '#a3231f', position: 'insideBottomRight' }} />
          <Line dataKey="potassium" stroke="#0b6b5b" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* contributing agents, split by direction */}
      <div className="k-agents">
        <div className="k-col">
          <div className="k-col-head raise">Raises K+ ({k.agents.n_raising})</div>
          {k.agents.raising.length === 0 && <div className="k-none">none</div>}
          {k.agents.raising.map((a, i) => (
            <div key={i} className="k-agent">
              <span className="k-agent-name">{a.drug}</span>
              <span className="k-agent-class">{a.class}</span>
              <span className="k-weight" title="relative contribution">{'●'.repeat(a.weight)}</span>
            </div>
          ))}
        </div>
        <div className="k-col">
          <div className="k-col-head lower">Lowers K+ ({k.agents.n_lowering})</div>
          {k.agents.lowering.length === 0 && <div className="k-none">none</div>}
          {k.agents.lowering.map((a, i) => (
            <div key={i} className="k-agent">
              <span className="k-agent-name">{a.drug}</span>
              <span className="k-agent-class">{a.class}</span>
              <span className="k-weight">{'●'.repeat(a.weight)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* suggested medicine actions */}
      {k.suggestions.length > 0 && (
        <>
          <div className="guide-links-title" style={{ marginTop: 14 }}>Suggested medicine review</div>
          <table className="flagtable">
            <thead><tr><th>Priority</th><th>Drug</th><th>Effect</th><th>Suggestion</th></tr></thead>
            <tbody>
              {k.suggestions.map((s, i) => (
                <tr key={i}>
                  <td><span className={'chip ' + (s.urgent ? 'urgent' : s.priority === 'review first' ? 'review' : '')}>
                    {s.priority}</span></td>
                  <td style={{ fontWeight: 600, textTransform: 'capitalize' }}>{s.drug}</td>
                  <td style={{ fontSize: 12, color: '#5c6b68' }}>{s.effect}</td>
                  <td style={{ fontSize: 12.5 }}>{s.suggestion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {k.actions.length > 0 && (
        <ul className="k-actions">
          {k.actions.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      )}

      {pred && pred.available && (
            <div className="k-mlrisk">
              <p><span>ML PREDICTED RISK</span></p>
              <p><span>{Math.round(pred.breach_probability * 100)}%</span></p>
              <p><span>chance of breach at next reading · {pred.model}
                {pred.likely_driver && <> · likely driver: <strong>{pred.likely_driver.drug}</strong></>}
              </span></p>
            </div>
          )}

      <div className="fc-foot">
        Thresholds: ≥5.5 action, ≥6.0 urgent · &lt;3.5 action, &lt;3.0 urgent.
        Contributing agents are drawn from current medicines only. Advisory — the pharmacist decides.
      </div>
    </div>
    
    




  )
}
