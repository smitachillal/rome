import { useState } from 'react'
import Tabs from './components/Tabs.jsx'
import PatientInformation from './pages/PatientInformation.jsx'
import ModelPrediction from './pages/ModelPrediction.jsx'
import Eda from './pages/Eda.jsx'
import Renal_Drug_Handbook from './pages/Renal_Drug_Handbook.jsx'
// import PotassiumRisk from './pages/PotassiumPanel.jsx'
import PotassiumModelDashboard from './pages/PotassiumModelDashboard.jsx'
const TABS = [
  { id: 'patient', label: 'Patients information', render: () => <PatientInformation /> },
  { id: 'prediction', label: 'AI Model prediction', render: () => <ModelPrediction /> },
  { id: 'renal_drug_handbook', label: 'Renal Drug Handbook', render: () => <Renal_Drug_Handbook /> },
  { id: 'potassium_model', label: 'Potassium model', render: () => <PotassiumModelDashboard /> }
  // { id: 'potassium_hyper_hypo_kalemia_risk', label: 'Potassium Hyper-Hypo Kalemia Risk', 
  //   render: () => <PotassiumRisk /> }
  // { id: 'eda', label: 'EDA Performance', render: () => <Eda /> }
  
]

export default function App() {
  const [active, setActive] = useState(TABS[0].id)
  const current = TABS.find(t => t.id === active)

  return (
    <>
      <header className="app-header">
        <h1>Renal Dose Adjustment</h1>
        <span className="env">Development build — sample data only</span>
      </header>

      <Tabs tabs={TABS} active={active} onChange={setActive} />

      <main className="tabpanel" id={`panel-${active}`} role="tabpanel" aria-labelledby={`tab-${active}`}>
        {current.render()}
      </main>
    </>
  )
}
