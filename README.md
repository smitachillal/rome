# Medication Safety CDSS — dashboard scaffold

React + Vite front end for a clinical decision support dashboard. Sample data only, no real patient records.

## Run it

```bash
npm install
npm run dev
```

Opens on http://localhost:5173

## Structure

```
src/
  App.jsx                    three-tab shell
  components/
    Tabs.jsx                 accessible tab strip (arrow keys work)
    PatientList.jsx          left-hand patient rail
    Section.jsx              numbered card wrapper
    panels/                  one file per section of the patient page
      PersonalInformation.jsx   1. personal information
      RenalFunction.jsx         2. eGFR, CrCl, AKI, CKD
      CurrentMedication.jsx     3. current medication
      RiskScore.jsx             4. risk score with SHAP contributions
      Alerts.jsx                5. alerts and flags
      MedicationIssues.jsx      6. possible medication issues
      PredictionExplanation.jsx 7. prediction explanation
  pages/
    PatientInformation.jsx   assembles list + sections
    ModelPrediction.jsx      placeholder
    Eda.jsx                  placeholder
  data/mockPatients.js       replace with FHIR R4 fetch layer
  styles/global.css          NHS design system palette as CSS variables
```

## Swapping in real data

Every panel takes plain props, so nothing needs rewriting when the API arrives. Replace the
import in `pages/PatientInformation.jsx`:

```js
// import { patients } from '../data/mockPatients.js'
const { patients, loading } = usePatients()   // your FHIR hook
```

Keep the shape in `mockPatients.js` as the contract between the front end and the API.

## Adding charts

Nothing is installed beyond React. For the Model prediction and EDA tabs:

```bash
npm install recharts
```
