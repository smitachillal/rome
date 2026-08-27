import React, { useEffect, useState } from 'react'
import { getMedications } from '../../api/client.js'

const STATUS = {
  current: { cls: 'ok', label: 'CURRENT' },
  stopped: { cls: '', label: 'STOPPED' },
  planned: { cls: 'review', label: 'PLANNED' },
  unknown: { cls: 'review', label: 'NO DATES' },
}

export default function MedicationTimeline({ patientId }) {
  const [m, setM] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    console.log("patientId in medication -> " , patientId)
    if (patientId == null) return
    setM(null); setErr(null)
    getMedications(patientId).then(setM).catch((e) => setErr(String(e)))
    console.log(" Medicines retreived ", m)
  }, [patientId])

  if (err) return <div className="rec-empty">Could not load medications ({err}).</div>
  if (!m) return <div className="rec-empty">Loading medications…</div>

  return (
    <>
     <style>{`
     .table-container {
        width: 100%;
        max-height: 200px;
        overflow: auto;
        border: 1px solid #ddd;
      }

      table {
        width: 100%;
        min-width:500px;
        border-collapse: collapse;
      }
     `}</style>
    
    <div className="table-container">
      
      <table  border='1' >
        <thead>
          <tr><th>Medicine</th><th>Start date</th><th>End date</th><th>Status</th></tr>
        </thead>
        <tbody>
          {m.medications.map((r, i) => {
            const st = STATUS[r.status] || STATUS.unknown
            return (
              <tr key={i} className={r.status === 'stopped' ? 'med-stopped' : ''}>
                <td style={{ fontWeight: 600, textTransform: 'capitalize' }}>{r.ingredient}</td>
                <td>{r.start_date || '—'}</td>
                <td>{r.end_date || '—'}</td>
                <td><span className={'chip ' + st.cls}>{st.label}</span></td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="fc-foot">
        Only <strong>current</strong> medicines are used for interaction checking —
        drugs that never overlapped in time cannot interact.
        {m.stopped.length > 0 && <> Excluded as historical: {[...new Set(m.stopped.map(d => d.toLowerCase()))].join(', ')}.</>}
      </div>
    </div>
    </>
  )
}
