export default function PersonalInformation({ patient }) {
  const bmi = (patient.weight_kg / Math.pow(patient.heightCm / 100, 2)).toFixed(1)

  return (
    <dl className="dl tabular">
      <div><dt>Name</dt><dd>{patient.name}</dd></div>
      <div><dt>Age</dt><dd>{patient.age}</dd></div>
      <div><dt>Sex</dt><dd>{patient.sex}</dd></div>
      <div><dt>Weight</dt><dd>{patient.weight_kg} kg</dd></div>
      <div><dt>CKD Status{" "}</dt><dd>{patient.ckd_confirmed === 0 ? "No CKD" : "CKD"} </dd></div>
      <div><dt>CKD Stage</dt><dd>{patient.ckd_stage} </dd></div>
      {/*<div><dt>Height</dt><dd>{patient.heightCm} cm</dd></div>
      <div><dt>BMI</dt><dd>{bmi}</dd></div>
       <div><dt>Location</dt><dd>{patient.ward}</dd></div>
      <div><dt>Admitted</dt><dd>{patient.admitted}</dd></div>
      <div>
        <dt>Conditions</dt>
        <dd>{patient.conditions.join(', ')}</dd>
      </div>
      <div>
        <dt>Allergies</dt>
        <dd>{patient.allergies.join(', ')}</dd>
      </div> */}
    </dl>
  )
}
