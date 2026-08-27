//import { useState } from 'react'
// import { patients } from '../data/mockPatients.js'
 import PatientList from '../components/PatientList.jsx'
// import Section from '../components/Section.jsx'
// import PersonalInformation from '../components/panels/PersonalInformation.jsx'
// import RenalFunction from '../components/panels/RenalFunction.jsx'
// import CurrentMedication from '../components/panels/CurrentMedication.jsx'
// import RiskScore from '../components/panels/RiskScore.jsx'
// import Alerts from '../components/panels/Alerts.jsx'
// import MedicationIssues from '../components/panels/MedicationIssues.jsx'
// import PredictionExplanation from '../components/panels/PredictionExplanation.jsx'

import { useEffect, useState } from "react";

export default function PatientInformation() {

   useEffect(() => {
    fetch("http://127.0.0.1:8000/api/patients")
      .then((response) => response.json())
      .then((data) => {
        console.log("Patients from API:", data);
        setPatients(data);
      })
      .catch((error) => {
        console.error("Error loading patients:", error);
      });
  }, []);

  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null)
  const patient = patients.find(p => p.id === selectedId)

  return (
    <div className="patient-layout">
      <PatientList patients={patients} selectedId={selectedId} onSelect={setSelectedId} />

      {!patient ? (
        <div className="empty">
          <h2>Select a patient</h2>
          <p>Choose a name from the list to see their record, renal function and medication risk.</p>
        </div>
      ) : (
        <div className="sections">
          <h2 style={{ margin: 0 }}>{patient.name}</h2>

          <Section number="1" title="Patient personal information">
            <PersonalInformation patient={patient} />
          </Section>

          <Section number="2" title="eGFR, CrCl, AKI and CKD">
            <RenalFunction renal={patient.renal} />
          </Section>

          <Section number="3" title="Current medication">
            <CurrentMedication medications={patient.medications} />
          </Section>

          <Section number="4" title="Risk score by SHAP">
            <RiskScore risk={patient.risk} />
          </Section>

          <Section number="5" title="Alerts and flags">
            <Alerts alerts={patient.alerts} />
          </Section>

          <Section number="6" title="Possible medication and related issues">
            <MedicationIssues issues={patient.issues} />
          </Section>

          <Section number="7" title="Prediction explanation">
            <PredictionExplanation text={patient.explanation} />
          </Section>
        </div>
      )}
    </div>
  )
}
