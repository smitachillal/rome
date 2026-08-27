// #import React, { useEffect, useState } from "react"; 

import React, { useState, useEffect, useCallback, useRef } from "react";


export default function CurrentMedication({ patient }) {
   const [drugs, setDrugs] = useState([]);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState(null);
  
//  const [data, setData] = useState(null);
   const [status, setStatus] = useState("loading"); // loading | ready | error
   const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    
    // Do not call the API if patient ID is not available
    if (!patient?.patient_id) {
     // setLoading(false);
      return;
    }
    // setStatus("loading");
    const fetchDrugs = async () => {
      try {
        //setLoading(true);

        const response = await fetch(
          `http://127.0.0.1:8000/api/patients/${patient.patient_id}/recommendations`
          // `http://127.0.0.1:8000/api/drugs/${patient.patient_id}`
        );

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        const data = await response.json();

        // Get drugs from API response
        setDrugs(data  || []);
        console.log("drugs drug_list from API:", data);
        //setStatus("ready");
        //console.log("getStatus", status)
      } catch (err) {
        console.error("Failed to fetch drugs:", err);
        // setError(err.message);
       // setStatus("error");
      } finally {
        
        //setLoading(false);
      }
    };

    fetchDrugs();
  }, [patient?.patient_id]) ;


  // // This runs AFTER React has updated status
  // useEffect(() => {
  //   console.log("Status changed:", status);
  // }, [status]);

  // if (loading) {
  //   return <div>Loading drugs...</div>;
  // }

  // if (error) {
  //   return <div>Drug not found</div>;
  // }

  if (!drugs ) {
    return <div>No drugs data available.</div>;
  }


const safetyStyles = {
  caution: "bg-amber-100 text-amber-800 border-amber-200",
  avoid: "bg-rose-100 text-rose-700 border-rose-200",
  safe: "bg-emerald-100 text-emerald-800 border-emerald-200",
};



function SafetyBadge({ safety }) {
  const cls = safetyStyles[safety] || safetyStyles.caution;
  return (
    <span
      className={`inline-block rounded-md border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${cls}`}
    >
      {safety}
    </span>
  );
}

function FitBar({ score, max }) {
  const pct = max > 0 ? Math.max(6, Math.round((score / max) * 100)) : 0;
  return (
    <div className="flex items-center gap-3">
      <div className="h-4 w-32 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-teal-800 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-slate-400">
        {Number(score).toFixed(3)}
      </span>
    </div>
  );
}






  return (

  
    
    <div className="min-h-screen bg-slate-50 p-6 font-sans text-slate-800">
      <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        {/* {status === "loading" && (
          <div className="animate-pulse space-y-4">
            <div className="h-4 w-64 rounded bg-slate-200" />
            <div className="h-3 w-full rounded bg-slate-100" />
            <div className="h-3 w-full rounded bg-slate-100" />
            <div className="h-3 w-5/6 rounded bg-slate-100" />
          </div>
        )} */}

        {/* {status === "error" && (
          <div className="rounded-xl border border-rose-100 bg-rose-50 px-5 py-4 text-sm text-rose-700">
            <p className="font-semibold">Couldn't load recommendations</p>
            <p className="mt-1 text-rose-600">{errorMsg}</p>
            <button
              onClick={load}
              className="mt-3 rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50"
            >
              Retry
            </button>
          </div>
        )} */}

        { drugs && !drugs.suggestions && (
          <p className="text-sm text-slate-500">
            No recommendations available for this patient.
          </p>
        )}
        <div>
        
        </div>
        {drugs && drugs.suggestions  && (
          <RecommendationsView data={drugs} />
        )}
        
      </div>
    </div> 
  )
}
// ---- Presentational view (pure, no fetching) ------------------------------
function RecommendationsView({ data }) {
  // const { best_model, suggestions = [], removed = [] } = data;
    const suggestions = data.suggestions || [];
    const removed = data.removed || [];

  const maxScore = Math.max(...suggestions.map((s) => s.ml_score), 0.0001);
  // handle event
  const [selectedMedicine, setSelectedMedicine] = useState(null);
  const [showPopup, setShowPopup] = useState(false);

  
  const closePopup = () => {
    setShowPopup(false);
    setSelectedMedicine(null);
  };
  const handleMedicineClick = async (drugName) => {
    console.log("Clicked:", drugName);
// Reference to the HTML dialog 
    // const dialogRef = useRef(null);
    try {
      const response = await fetch("drugs.json");

      if (!response.ok) {
        throw new Error("Could not load JSON file");
      }

      const medicines = await response.json();
      console.log(" MEDICINE JSON " ,  medicines)
      const result = medicines.find(
        (medicine) =>
          medicine.Drug_name?.toLowerCase() ===
          drugName?.toLowerCase()
      );

      console.log("Found:", result);

      const popup = window.open(
      "",
      "_blank",
      "width=800,height=600,resizable=yes,scrollbars=yes"
    );
     if (!popup) {
      alert("Popup was blocked by the browser.");
      return;
    }

    const escapeHtml = (value) => {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    };


// Converts text containing • bullets into HTML
  const formatMedicineText = (value) => {
      if (!value) {
        return "<p class='empty'>—</p>";
      }

      const text = String(value).trim();

      // If the text contains bullets
      if (text.includes("•")) {
        const parts = text
          .split("•")
          .map((item) => item.trim())
          .filter(Boolean);

        return `
          <ul>
            ${parts
              .map((item) => `<li>${escapeHtml(item)}</li>`)
              .join("")}
          </ul>
        `;
      }

      // Normal text
      return `<p>${escapeHtml(text)}</p>`;
    };


  popup.document.write(`
        <!DOCTYPE html>
        <html>
        <head>

          <title>${escapeHtml(result.Drug_name)}</title>

          <style>

            * {
              box-sizing: border-box;
            }

            body {
              margin: 0;
              padding: 30px;
              font-family: Arial, Helvetica, sans-serif;
              background: #ffffff;
              color: #333;
              line-height: 1.5;
            }

            .container {
              max-width: 1200px;
              margin: 0 auto;
            }

            .drug-name {
              font-size: 28px;
              font-weight: 500;
              color: #222;
              margin: 0 0 8px 0;
              padding-bottom: 12px;
              border-bottom: 1px solid #ddd;
            }

            .section {
              margin-top: 22px;
            }

            .section-title {
              color: #0066cc;
              font-size: 15px;
              font-weight: bold;
              margin-bottom: 8px;
            }

            .section p {
              margin: 0;
              font-size: 13px;
              color: #444;
            }

            .section ul {
              margin: 5px 0 0 20px;
              padding: 0;
            }

            .section li {
              margin-bottom: 7px;
              font-size: 13px;
              color: #444;
            }

            .empty {
              color: #999;
            }

            .close-button {
              position: fixed;
              right: 20px;
              top: 15px;
              border: none;
              background: #0066cc;
              color: white;
              padding: 8px 14px;
              border-radius: 5px;
              cursor: pointer;
            }

            .close-button:hover {
              background: #004c99;
            }

          </style>

        </head>

        <body>

          <div class="container">

            <h1 class="drug-name">
              ${escapeHtml(result.Drug_name)}
            </h1>


            <div class="section">
              <div class="section-title">
                Clinical Use
              </div>

              ${formatMedicineText(result.Clinical_use)}
            </div>


            <div class="section">
              <div class="section-title">
                Dose in Normal Renal Function
              </div>

              ${formatMedicineText(
                result.Dose_in_normal_renal_function
              )}
            </div>


            <div class="section">
              <div class="section-title">
                Pharmacokinetics
              </div>

              ${formatMedicineText(result.Pharmacokinetics)}
            </div>


            <div class="section">
              <div class="section-title">
                Metabolism
              </div>

              ${formatMedicineText(result.Metabolism)}
            </div>


            <div class="section">
              <div class="section-title">
                Dose in Renal Impairment
              </div>

              ${formatMedicineText(
                result.Dose_in_renal_impairment_GFR_mL_min
              )}
            </div>


            <div class="section">
              <div class="section-title">
                Renal Replacement Therapies
              </div>

              ${formatMedicineText(
                result.Dose_in_patients_undergoing_renal_replacement_therapies
              )}
            </div>


            <div class="section">
              <div class="section-title">
                Drug Interactions
              </div>

              ${formatMedicineText(
                result.Important_drug_interactions
              )}
            </div>


            <div class="section">
              <div class="section-title">
                Administration
              </div>

              ${formatMedicineText(result.Administration)}
            </div>


            <div class="section">
              <div class="section-title">
                Other Information
              </div>

              ${formatMedicineText(result.Other_information)}
            </div>

          </div>

        </body>
        </html>
      `);

      popup.document.close();
    // };



    // Put result into the new window
    // popup.document.body.innerHTML = `
    //   <h2>${drugName}</h2>
    //   <pre style="
    //     white-space: pre-wrap;
    //     font-family: monospace;
    //     padding: 20px;
    //   ">${JSON.stringify(result, null, 2)}</pre>
    // `;
      // setSelectedMedicine(result);
      // dialogRef.current?.showModal();
      // if (result) {
      //   console.log('In result fun')
      //   setSelectedMedicine(result);
      //   setShowPopup(true);
      // }
    } catch (error) {
      console.error(error);
    }
   };

  return (
    <>
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-baseline gap-2">
        {/* <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
          Medicine Recommendations
        </h2> */}
        {/* {best_model && (
          <>
            <span className="text-slate-300">·</span>
            <span className="text-sm font-semibold text-teal-700">
              {best_model}
            </span>
          </>
        )} */}
      </div>
<div>

</div>
      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left" width="70%" border="1">
          <thead>
            <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <th className="py-3 pr-4 font-semibold">Drug</th>
              <th className="py-3 pr-4 font-semibold">Fit</th>
              <th className="py-3 pr-4 font-semibold">Indication</th>
              <th className="py-3 pr-4 font-semibold">Safety</th>
              <th className="py-3 font-semibold">Dose guidance</th>
              <th className="py-3 font-semibold">Handbook guidance</th>
            </tr>
          </thead>
          <tbody>
            {suggestions.map((s) => (
              <tr
                key={s.drug}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
              >
                <td className="py-4 pr-4 font-semibold capitalize text-slate-900">
                  {s.drug}
                </td>
                <td className="py-4 pr-4">
                  {/* <FitBar score={s.ml_score} max={maxScore} /> */}
                  {s.ml_score}
                </td>
                <td className="py-4 pr-4 capitalize text-slate-600">
                  {s.indication}
                </td>
                <td className="py-4 pr-4">
                  {/* <SafetyBadge safety={s.safety} /> */}
                  {s.safety}
                </td>
                <td className="py-4 text-slate-500" title={s.reference}>
                  {s.dose_guidance}
                </td>
                <td className="py-4 text-slate-500" >
                  <button onClick={() => handleMedicineClick(s.drug)}>
                    View Handbook
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Removed banner */}
      {removed.length > 0 && (
        <div className="mt-6 rounded-xl border border-rose-100 bg-rose-50 px-5 py-4 text-sm text-rose-700">
          <span className="font-bold">Removed (renally unsafe): </span>
          {removed.map((r, i) => (
            <span key={r.drug}>
              <span className="font-medium" title={r.dose_guidance}>
                {r.drug}
              </span>
              {i < removed.length - 1 ? ", " : ""}
            </span>
          ))}
        </div>
      )}

      {/* Footnote */}
      <p className="mt-6 border-t border-slate-100 pt-4 text-xs leading-relaxed text-slate-400">
        <b>Suggestions are ML-ranked by fit to the patient, then screened against
        the Renal Drug Handbook at the patient's eGFR. Advisory only — the
        pharmacist decides.</b>
      </p>
    </>
  );
}