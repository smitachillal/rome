import React, { useEffect, useState } from 'react'
import { getInteractions } from '../../api/client.js'

const SEV = {
  Major:    { color: '#b83280', bg: '#fbe9f2', label: 'Major' },
  Moderate: { color: '#b26a00', bg: '#fdf1df', label: 'Moderate' },
  Minor:    { color: '#2f855a', bg: '#e6f4ec', label: 'Minor' },
  Unknown:  { color: '#94a3b8', bg: '#eef2f4', label: 'Unknown' },
}
const NODE_FILL = ['#4a7fb5', '#3a9e78', '#b06a9e', '#c98a3a', '#6a8caf', '#8a7bb0']

// lay nodes out on a circle
function layout(nodes, w, h) {
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 60
  const pos = {}
  nodes.forEach((n, i) => {
    const ang = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2
    pos[n.id] = { x: cx + r * Math.cos(ang), y: cy + r * Math.sin(ang) }
  })
  return pos
}

export default function InteractionGraph({ patientId }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (patientId == null) return
    setData(null); setErr(null)
    getInteractions(patientId).then(setData).catch((e) => setErr(String(e)))
  }, [patientId])

  if (err) return <div className="rec-empty">Could not load interactions ({err}).</div>
  if (!data) return <div className="rec-empty">Loading interactions…</div>
  if (data.n_drugs < 2)
    return <div className="section"><h3>Drug interactions</h3>
      <div className="rec-empty">Need at least two drugs to check interactions.</div></div>

  const W = 520, H = 320
  const pos = layout(data.nodes, W, H)

  return (
    <div className="section">
      {/* legend / counts */}
      <div className="ddi-legend">
        {['Major', 'Moderate', 'Minor', 'Unknown'].map((s) => (
          <span key={s} className="ddi-leg">
            <span className="ddi-dot" style={{ background: SEV[s].color }} />
            {SEV[s].label}({data.counts[s] || 0})
          </span>
        ))}
      </div>

      {/* network graph */}
      <div className="ddi-graph">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
          {data.edges.map((e, i) => {
            const a = pos[e.source], b = pos[e.target]
            if (!a || !b) return null
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={SEV[e.severity].color} strokeWidth={e.severity === 'Unknown' ? 2 : 3.5}
              strokeDasharray={e.severity === 'Unknown' ? '5 5' : '0'} strokeOpacity={0.8} />
          })}
          {data.nodes.map((n, i) => (
            <g key={n.id}>
              <circle cx={pos[n.id].x} cy={pos[n.id].y} r={34}
                fill={NODE_FILL[i % NODE_FILL.length]} stroke="#fff" strokeWidth={3} />
              <text x={pos[n.id].x} y={pos[n.id].y + 4} textAnchor="middle"
                fill="#fff" fontSize={12} fontWeight={600}>{n.label}</text>
            </g>
          ))}
        </svg>
      </div>

      {/* detail cards */}
      <div className="ddi-cards" style={{ overflow: "auto", maxHeight : "200px"}}>
        {data.pairs.map((p, i) => {
          const sv = SEV[p.severity]
          return (
            <div key={i} className="ddi-card" style={{ borderLeftColor: sv.color }}>
              <div className="ddi-card-head">
                <span className="ddi-badge" style={{ background: sv.color }}>{p.severity}</span>
                <span className="ddi-pair">{p.drug_a} ⭤ {p.drug_b}</span>
                {p.source && <span className="ddi-source">{p.source}</span>}
              </div>
              <p className="ddi-line"><strong>Interaction:</strong> {p.interaction || '—'}</p>
              <p className="ddi-line"><strong>Management:</strong> {p.management || '—'}</p>
            </div>
          )
        })}
      </div>
      <div className="fc-foot">
        Severity-graded interactions. “Unknown” means no record in this source — not
        proof of safety. Advisory only.
      </div>
    </div>
  )
}
