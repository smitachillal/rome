import React, { useEffect, useState } from "react"; 

// const prescriptions = [
//   {
//     subject_id: 10040025,
//     starttime: "2147-11-09 12:00:00",
//     stoptime: "2147-11-12 11:00:00",
//     drug_type: "BASE",
//     drug: "Vial",
//     prod_strength: "Send Vial",
//     dose_val_rx: "1",
//     dose_unit_rx: "VIAL",
//     form_unit_disp: "VIAL",
//     doses_per_24_hrs: 2,
//   },
// ];

export default function CurrentMedication({ patient }) {
  const [prescriptions, setPrescriptions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    useEffect(() => {
      // Do not call the API if patient ID is not available
      if (!patient?.patient_id) {
        setLoading(false);
        return;
      }
  
      const fetchDrugs = async () => {
        try {
          setLoading(true);
  
          const response = await fetch(
            `http://127.0.0.1:8000/api/alldrugs/${patient.patient_id}`
          );
  
          if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
          }
  
          const data = await response.json();
  
          setPrescriptions(data || []);
          console.log("drug details from API:", data);
        } catch (err) {
          console.error("Failed to fetch drug details:", err);
          setError(err.message);
        } finally {
          setLoading(false);
        }
      };
  
      fetchDrugs();
    }, [patient?.patient_id]) ;
  
    if (loading) {
      return <div>Loading renal trend...</div>;
    }
  
    if (error) {
      return <div>Error loading data: {error}</div>;
    }
  
    if (!prescriptions.length) {
      return <div>No prescriptions data available.</div>;
    }


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

      // th,
      // td {
      //   padding: 10px;
      //   border: 1px solid #ddd;
      //   text-align: left;
      //   white-space: nowrap;
      // }

      // thead th {
      //   position: sticky;
      //   top: 0;
      //   background: white;
      //   //z-index: 1;
      // }
    `}</style>
    

    
    <div className="table-container">
      <table border='1'>
        <thead>
          <tr>
            <th>Start Time</th>
            <th>Stop Time</th>
            {/* <th>Drug Type</th> */}
            <th>Drug</th>
            <th>Product Strength</th>
            {/* <th>Dose Value</th>
            <th>Dose Unit</th>
            <th>Form Unit</th> */}
            <th>Doses / 24 Hrs</th>
          </tr>
        </thead>

        <tbody>
          {prescriptions.map((prescription, index) => (
            <tr key={index}>
              {/* <td>{prescription.subject_id}</td> */}
              <td>{prescription.starttime}</td>
              <td>{prescription.stoptime}</td>
              {/* <td>{prescription.drug_type}</td> */}
              <td>{prescription.drug}</td>
              <td>{prescription.prod_strength}</td>
              {/* <td>{prescription.dose_val_rx}</td>
              <td>{prescription.dose_unit_rx}</td>
              <td>{prescription.form_unit_disp}</td> */}
              <td>{prescription.doses_per_24_hrs}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </>
  ); 
  
}
