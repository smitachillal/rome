
import { useMemo, useState } from "react";

import {
  Box,
  Paper,
  List,
  ListItemButton,
  ListItemText,
  TextField,
  Typography,
  Divider,
} from "@mui/material";

 import drugs from "../data/drugs.json";

export default function Renal_Drug_Handbook() {
  

  const [search, setSearch] = useState("");
  const [selectedDrug, setSelectedDrug] = useState(drugs[0]);

  const filteredDrugs = useMemo(() => {
    return drugs.filter((drug) =>
      drug.Drug_name.toLowerCase().includes(search.toLowerCase())
    );
  }, [search]);

  return (
    <Box
      sx={{
        width: "100%",
        height: "100vh",
        p: 2,
        boxSizing: "border-box",
      }}
    >
      <Typography variant="h4" gutterBottom>
        Renal Drug Handbook
      </Typography>

      <TextField
        fullWidth
        placeholder="Search medicine..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2 }}
      />

      <Box
        sx={{
          display: "flex",
          gap: 2,
          height: "calc(100vh - 150px)",
        }}
      >
        {/* LEFT PANEL */}
        <Paper
          elevation={3}
          sx={{
            width: 300,
            overflowY: "auto",
            flexShrink: 0,
          }}
        >
          <List>
            {filteredDrugs.map((drug) => (
              <ListItemButton
                key={drug.Drug_name}
                selected={selectedDrug?.Drug_name === drug.Drug_name}
                onClick={() => setSelectedDrug(drug)}
              >
                <ListItemText primary={drug.Drug_name} />
              </ListItemButton>
            ))}
          </List>
        </Paper>

        {/* RIGHT PANEL */}
        <Paper
          elevation={3}
          sx={{
            flexGrow: 1,
            overflowY: "auto",
            p: 3,
          }}
        >
          {selectedDrug ? (
            <>
              <Typography variant="h4" gutterBottom>
                {selectedDrug.Drug_name}
              </Typography>

              <Divider sx={{ mb: 3 }} />

              <Section
                title="Clinical Use"
                value={selectedDrug.Clinical_use}
              />

              <Section
                title="Dose in Normal Renal Function"
                value={selectedDrug.Dose_in_normal_renal_function}
              />

              <Section
                title="Pharmacokinetics"
                value={selectedDrug.Pharmacokinetics}
              />

              <Section
                title="Metabolism"
                value={selectedDrug.Metabolism}
              />

              <Section
                title="Dose in Renal Impairment"
                value={selectedDrug.Dose_in_renal_impairment_GFR_mL_min.replace(/\.\s*/g, ".\n")}
              />

              <Section
                title="Renal Replacement Therapies"
                value={
                  selectedDrug
                    .Dose_in_patients_undergoing_renal_replacement_therapies.replace(/\.\s*/g, ".\n")
                }
              />

              <Section
                title="Drug Interactions"
                value={selectedDrug.Important_drug_interactions}
              />

              <Section
                title="Administration"
                value={selectedDrug.Administration}
              />

              <Section
                title="Other Information"
                value={selectedDrug.Other_information}
              />

              {/* <Section
                title="ML Parameters"
                value={selectedDrug.ml_params_for_AI}
              /> */}
            </>
          ) : (
            <Typography>Select a medicine</Typography>
          )}
        </Paper>
      </Box>
    </Box>
  );
}

function Section({ title, value }) {
  return (
    <Box sx={{ mb: 4 }}>
      <Typography
        variant="h6"
        sx={{
          color: "#1565c0",
          fontWeight: 700,
          mb: 1,
        }}
      >
        {title}
      </Typography>

      <Typography
        sx={{
          whiteSpace: "pre-wrap",
          lineHeight: 1.8,
        }}
      >
        {value || "-"}
      </Typography>
    </Box>
  );
}