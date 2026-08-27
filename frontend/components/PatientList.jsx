export default function PatientList({ patients, selectedId, onSelect }) {
  return (
    <nav className="patient-list" aria-label="Patient list">
      <h2>Patients ({patients.length})</h2>
      
      <ul>
        {patients.map(p => (
          <li key={p.patient_id}>
            <button
              type="button"
              aria-current={p.patient_id === selectedId}
              onClick={() => { console.log("Clicked patient ID:", p.patient_id); onSelect(p.patient_id) }  }
            >
              <span className="pname">{p.name}</span>
              <span className="pmeta">{p.age} · {p.sex} · {p.ward}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
