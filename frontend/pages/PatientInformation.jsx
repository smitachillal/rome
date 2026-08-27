//import { useState } from 'react'
// import { patients } from '../data/mockPatients.js'
 import PatientList from '../components/PatientList.jsx'
 import Section from '../components/Section.jsx'
 import PersonalInformation from '../components/panels/PersonalInformation.jsx'
 import RenalFunction from '../components/panels/RenalFunction.jsx'
 import CurrentMedication from '../components/panels/CurrentMedication.jsx'
 import AllMedication from '../components/panels/AllMedication.jsx'
 
import RiskScore from '../components/panels/RiskScore.jsx'
import Alerts from '../components/panels/Alerts.jsx'
import MedicationIssues from '../components/panels/MedicationIssues.jsx'
import PredictionExplanation from '../components/panels/PredictionExplanation.jsx'
import ForecastChart from '../components/panels/ForecastChart.jsx'
import GuidancePanel from '../components/panels/GuidancePanel.jsx'

import { useEffect, useState } from "react";
import InteractionGraph from '../components/panels/InteractionGraph.jsx'

import MedicationTimeline from '../components/panels/MedicationTimeline.jsx'

import Potassium from '../components/panels/PotassiumPanel.jsx'

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
  const patient = patients.find(p => p.patient_id === selectedId)

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

          <Section number="2" title="Patient eGFR and CrCl trajectory graph">
            <RenalFunction patient={patient} />
          </Section>

          <Section number="3" title="Complete Drugs History">
            <AllMedication patient={patient} />
          </Section>

          <Section number="4" title="Renal Drugs Suggestions">
            <CurrentMedication patient={patient} />
          </Section>


          <Section number="5" title="Renal Drugs History">
            <MedicationTimeline patientId={patient.patient_id} />
          </Section>

          {/* <Section number="5" title="Risk score by SHAP/NICE/Any other NHS/British Guideline">
            <RiskScore risk={patient} />
          </Section> */}

          <Section number="6" title="EGFR Forecast - Time to Breach">
            <ForecastChart patientId={patient.patient_id} />
          </Section>

          <Section number="7" title="Drug Drug Interaction details">
            <InteractionGraph patientId={patient.patient_id} />
          </Section>

          <Section number="8" title="UK clinical guidance (NICE / NHS / BNF)">
            <GuidancePanel patientId={patient.patient_id}/>
          </Section> 

          <Section number="9" title="Potassium Hyper-Hypo Kalemia Risk">
            <Potassium patientId={patient.patient_id}/>
          </Section> 
        </div>
      )}
    </div>
  )
}
