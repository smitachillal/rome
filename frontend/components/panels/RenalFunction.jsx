import React, { useEffect, useState } from "react"; 
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, } from "recharts";

// import { useEffect, useState } from "react";

// useEffect(() => {
//     fetch("http://127.0.0.1:8000/api/patients/{ patient.patient_id }")
//       .then((response) => response.json())
//       .then((data) => {
//         console.log("Patient eGFR data from API:", data);
//         setPatients(data);
//       })
//       .catch((error) => {
//         console.error("Error loading patients:", error);
//       });
//     }, []);
//   const [patients, setPatients] = useState([]);



export default function RenalFunction({ patient }) {

  const [trajectory, setTrajectory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Do not call the API if patient ID is not available
    if (!patient?.patient_id) {
      setLoading(false);
      return;
    }

    const fetchTrajectory = async () => {
      try {
        setLoading(true);

        const response = await fetch(
          `http://127.0.0.1:8000/api/patients/${patient.patient_id}`
        );

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        const data = await response.json();

        // Get trajectory from API response
        setTrajectory(data.trajectory || []);
        console.log("trajectory from API:", data.trajectory);
      } catch (err) {
        console.error("Failed to fetch trajectory:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTrajectory();
  }, [patient?.patient_id]) ;

  if (loading) {
    return <div>Loading renal trend...</div>;
  }

  if (error) {
    return <div>Error loading data: {error}</div>;
  }

  if (!trajectory.length) {
    return <div>No trajectory data available.</div>;
  }

return (
    <div
      style={{
        width: "100%",
        maxWidth: "600px",
        height: "280px",
        background: "#ffffff",
        borderRadius: "12px",
        padding: "12px",
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.08)",
      }}
    >
      <h3
        style={{
          margin: "0 0 8px",
          fontSize: "15px",
          color: "#374151",
        }}
      >
        Renal Function Trend
      </h3>

      <ResponsiveContainer width="100%" height="90%">
        <LineChart
          data={trajectory}
          margin={{
            top: 5,
            right: 15,
            left: 0,
            bottom: 5,
          }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#e5e7eb"
          />

          <XAxis
            dataKey="measured_on"
            tick={{ fontSize: 10 }}
            tickFormatter={(date) => date.substring(0, 7)}
          />

          <YAxis
            tick={{ fontSize: 10 }}
            width={35}
          />

          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid #e5e7eb",
              fontSize: "12px",
            }}
          />

          <Legend
            wrapperStyle={{
              fontSize: "12px",
            }}
          />

          <Line
            type="monotone"
            dataKey="egfr"
            name="eGFR"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 2 }}
            activeDot={{ r: 5 }}
          />

          <Line
            type="monotone"
            dataKey="crcl"
            name="CrCl"
            stroke="#16a34a"
            strokeWidth={2}
            dot={{ r: 2 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );

}