import React, { useEffect, useState } from 'react'
import { getGuidance } from '../../api/client.js'

const ROLES = [
  { id: 'patient', label: 'Patient' },
  { id: 'nurse', label: 'Nurse' },
  { id: 'pharmacist', label: 'Pharmacist' },
  { id: 'doctor', label: 'Doctor' },
]

export default function GuidancePanel({ patientId }) {
  const [role, setRole] = useState('pharmacist')
  const [g, setG] = useState(null)
  const [err, setErr] = useState(null)
  const [modal, setModal] = useState(false)

  useEffect(() => {
    if (patientId == null) return
    setG(null); setErr(null)
    getGuidance(patientId, role).then(setG).catch((e) => setErr(String(e)))
  }, [patientId, role])

  return (
    <div className="section">
      {/* role selector */}
      <div className="role-tabs">
        {ROLES.map((r) => (
          <button key={r.id}
            className={'role-tab' + (role === r.id ? ' active' : '')}
            onClick={() => setRole(r.id)}>{r.label}</button>
        ))}
      </div>

      {err && <div className="rec-empty">Could not load guidance ({err}).</div>}
      {!g && !err && <div className="rec-empty">Loading guidance…</div>}

      {g && (
        <>
          {/* short in-app note */}
          <div className="guide-note">{g.note}</div>

          {/* links out */}
          <div className="guide-links">
            <div className="guide-links-title">Official guidance</div>
            {g.resources.map((r, i) => (
              <a key={i} href={r.url} target="_blank" rel="noopener noreferrer" className="guide-link">
                {r.label} <span className="ext">↗</span>
              </a>
            ))}
          </div>

          {g.drug_links.length > 0 && (
            <div className="guide-links">
              <div className="guide-links-title">Per-drug pages</div>
              

              {[...new Map(g.drug_links.map(d => [d.label, d])).values()].map((d, i) => (
                <a
                  key={i}
                  href={d.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="guide-link drug"
                >
                  {d.label} <span className="ext">↗</span>
                </a>
              ))}

              {/* {
              
                g.drug_links.map((d, i) => (
                <a key={i} href={d.url} target="_blank" rel="noopener noreferrer" className="guide-link drug">
                  {d.label} <span className="ext">↗</span>
                </a>
              ))} */}
            </div>
          )}

          <button className="guide-more" onClick={() => setModal(true)}>
            View guidance summary
          </button>

          <div className="guide-disclaimer">{g.disclaimer}</div>
        </>
      )}

      {/* popup / modal */}
      {modal && g && (
        <div className="modal-backdrop" onClick={() => setModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <span>Guidance for: {ROLES.find((r) => r.id === role).label}</span>
              <button className="modal-x" onClick={() => setModal(false)}>×</button>
            </div>
            <p className="guide-note">{g.note}</p>
            <div className="guide-links-title">Open official sources</div>
            {/* {[...g.resources, ...g.drug_links].map((r, i) => (
              <a key={i} href={r.url} target="_blank" rel="noopener noreferrer" className="guide-link">
                {r.label} <span className="ext">↗</span>
              </a>
            ))} */}

                {[...new Map(
                  [...g.resources, ...g.drug_links].map(r => [r.label, r])
                ).values()].map((r, i) => (
                  <a
                    key={i}
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="guide-link"
                  >
                    {r.label} <span className="ext">↗</span>
                  </a>
                ))}
            
            <div className="guide-disclaimer">{g.disclaimer}</div>
          </div>
        </div>
      )}
    </div>
  )
}
