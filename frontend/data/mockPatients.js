// Placeholder data only — no real patient records.
// Replace this module with a FHIR R4 fetch layer when the API is ready.

export const patients = [
  {
    id: 'P-1001',
    name: 'Aisha Rahman',
    nhsNumber: '999 000 1001',
    age: 74,
    sex: 'Female',
    weightKg: 62,
    heightCm: 158,
    ward: 'Care of the Elderly, Ward 12',
    admitted: '2026-07-14',
    conditions: ['Type 2 diabetes', 'Hypertension', 'CKD stage 3b'],
    allergies: ['Penicillin (rash)'],

    renal: {
      creatinine: 148,          // umol/L
      eGFR: 34,                 // mL/min/1.73m2
      eGFRTrend: 'Falling — was 41 on 2026-06-02',
      crCl: 29,                 // mL/min, Cockcroft-Gault
      ckdStage: 'G3b A2',
      akiStage: 'AKI 1',
      akiFlag: true,
      lastMeasured: '2026-07-20'
    },

    medications: [
      { drug: 'Metformin', dose: '1 g', route: 'PO', frequency: 'BD', started: '2019-03-11', renalReview: true },
      { drug: 'Ramipril', dose: '5 mg', route: 'PO', frequency: 'OD', started: '2021-08-02', renalReview: true },
      { drug: 'Ibuprofen', dose: '400 mg', route: 'PO', frequency: 'TDS PRN', started: '2026-07-15', renalReview: true },
      { drug: 'Atorvastatin', dose: '20 mg', route: 'PO', frequency: 'ON', started: '2020-01-19', renalReview: false }
    ],

    risk: {
      score: 0.78,
      band: 'High',
      outcome: 'Medication-related renal deterioration within 30 days',
      modelVersion: 'xgb-v0.4',
      shap: [
        { feature: 'eGFR 34 mL/min/1.73m²', value: 0.21 },
        { feature: 'NSAID + ACE inhibitor combination', value: 0.18 },
        { feature: 'Metformin at reduced eGFR', value: 0.12 },
        { feature: 'Age 74', value: 0.07 },
        { feature: 'Serum potassium within range', value: -0.05 },
        { feature: 'No prior AKI admission', value: -0.09 }
      ]
    },

    alerts: [
      { level: 'high', title: 'Triple whammy combination', detail: 'Ramipril, a diuretic history and ibuprofen together raise AKI risk. Review the NSAID first.' },
      { level: 'high', title: 'Metformin below eGFR threshold', detail: 'eGFR 34 mL/min/1.73m². BNF advises review of dose below 45 and stopping below 30.' },
      { level: 'moderate', title: 'Creatinine rising', detail: 'Up 38% in 14 days. Meets AKI stage 1 criteria.' }
    ],

    issues: [
      { drug: 'Ibuprofen', issue: 'Nephrotoxicity in reduced renal function', action: 'Stop and switch to paracetamol', source: 'BNF' },
      { drug: 'Metformin', issue: 'Lactic acidosis risk below eGFR 30', action: 'Reduce to 500 mg BD and recheck U&E in 48h', source: 'dm+d / BNF' },
      { drug: 'Ramipril', issue: 'Hyperkalaemia and further eGFR fall', action: 'Hold during acute illness, monitor potassium', source: 'SIDER' }
    ],

    explanation:
      'The model puts this patient in the high band mainly because reduced renal function coincides with three drugs that each load the kidney. The NSAID started five days ago is the single largest modifiable contributor — removing it lowers the predicted risk to roughly 0.46. Stable potassium and no previous AKI admission pull the score down but do not offset the drug combination.'
  },

  {
    id: 'P-1002',
    name: 'Thomas Whitfield',
    nhsNumber: '999 000 1002',
    age: 58,
    sex: 'Male',
    weightKg: 91,
    heightCm: 178,
    ward: 'Acute Medical Unit, Bay 3',
    admitted: '2026-07-19',
    conditions: ['Atrial fibrillation', 'Heart failure (HFrEF)'],
    allergies: ['None recorded'],

    renal: {
      creatinine: 96,
      eGFR: 78,
      eGFRTrend: 'Stable',
      crCl: 92,
      ckdStage: 'G2 A1',
      akiStage: 'No AKI',
      akiFlag: false,
      lastMeasured: '2026-07-21'
    },

    medications: [
      { drug: 'Apixaban', dose: '5 mg', route: 'PO', frequency: 'BD', started: '2024-11-04', renalReview: true },
      { drug: 'Bisoprolol', dose: '2.5 mg', route: 'PO', frequency: 'OD', started: '2024-11-04', renalReview: false },
      { drug: 'Furosemide', dose: '40 mg', route: 'PO', frequency: 'OD', started: '2025-02-17', renalReview: true }
    ],

    risk: {
      score: 0.31,
      band: 'Moderate',
      outcome: 'Medication-related adverse event within 30 days',
      modelVersion: 'xgb-v0.4',
      shap: [
        { feature: 'Anticoagulant on board', value: 0.14 },
        { feature: 'Loop diuretic with AF', value: 0.08 },
        { feature: 'eGFR 78 mL/min/1.73m²', value: -0.11 },
        { feature: 'No renal impairment history', value: -0.07 }
      ]
    },

    alerts: [
      { level: 'moderate', title: 'Bleeding risk review due', detail: 'Apixaban with no HAS-BLED assessment recorded in the last 12 months.' },
      { level: 'info', title: 'Electrolytes due', detail: 'U&E last taken 3 days ago while on a loop diuretic.' }
    ],

    issues: [
      { drug: 'Furosemide', issue: 'Hypokalaemia and dehydration', action: 'Check U&E, review daily weights', source: 'BNF' },
      { drug: 'Apixaban', issue: 'Dose depends on age, weight and creatinine', action: 'Confirm 5 mg BD still correct at next review', source: 'dm+d' }
    ],

    explanation:
      'Risk sits in the moderate band. Preserved renal function is the strongest protective factor, so the score is driven almost entirely by the anticoagulant and diuretic rather than by kidney impairment. No single change would move the patient out of the band on its own.'
  },

  {
    id: 'P-1003',
    name: 'Grace Okonkwo',
    nhsNumber: '999 000 1003',
    age: 66,
    sex: 'Female',
    weightKg: 70,
    heightCm: 165,
    ward: 'Renal Outpatients',
    admitted: '2026-07-21',
    conditions: ['CKD stage 4', 'Anaemia of chronic kidney disease'],
    allergies: ['Codeine (nausea)'],

    renal: {
      creatinine: 212,
      eGFR: 22,
      eGFRTrend: 'Slow decline over 18 months',
      crCl: 24,
      ckdStage: 'G4 A3',
      akiStage: 'No AKI',
      akiFlag: false,
      lastMeasured: '2026-07-21'
    },

    medications: [
      { drug: 'Amlodipine', dose: '10 mg', route: 'PO', frequency: 'OD', started: '2022-05-30', renalReview: false },
      { drug: 'Ferrous fumarate', dose: '210 mg', route: 'PO', frequency: 'BD', started: '2025-09-12', renalReview: false },
      { drug: 'Alfacalcidol', dose: '0.25 mcg', route: 'PO', frequency: 'OD', started: '2026-01-08', renalReview: true }
    ],

    risk: {
      score: 0.54,
      band: 'Moderate',
      outcome: 'Medication-related adverse event within 30 days',
      modelVersion: 'xgb-v0.4',
      shap: [
        { feature: 'eGFR 22 mL/min/1.73m²', value: 0.26 },
        { feature: 'CKD stage 4', value: 0.11 },
        { feature: 'No nephrotoxic drugs prescribed', value: -0.14 },
        { feature: 'Regular renal follow-up', value: -0.08 }
      ]
    },

    alerts: [
      { level: 'moderate', title: 'Avoid nephrotoxics', detail: 'At eGFR 22, flag any NSAID, aminoglycoside or contrast exposure before it is prescribed.' },
      { level: 'info', title: 'Vitamin D monitoring', detail: 'Check adjusted calcium and phosphate with alfacalcidol.' }
    ],

    issues: [
      { drug: 'Alfacalcidol', issue: 'Hypercalcaemia', action: 'Monitor adjusted calcium every 3 months', source: 'BNF' },
      { drug: 'Ferrous fumarate', issue: 'Poor tolerance, constipation', action: 'Review if symptoms persist', source: 'SIDER' }
    ],

    explanation:
      'Low eGFR is the dominant contributor and it is not modifiable through prescribing. The current regimen contains no nephrotoxic agents, which is what keeps this patient out of the high band despite stage 4 disease. The model is effectively flagging the patient for careful future prescribing rather than a change today.'
  }
];
