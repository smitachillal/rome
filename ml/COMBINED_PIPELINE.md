# Combined suggestion pipeline — "ML proposes, rules dispose"

Two layers, each doing the job it is suited to:

```
patient (eGFR, CrCl, AKI, CKD, dx) 
   │
   ▼  ml/pipelines/prescribing_model.py   (learned from MIMIC prescribing)
ML ranks candidate drugs by prescribing likelihood
   │
   ▼  ml/pipelines/handbook_safety.py     (authoritative reference rules)
handbook screens each at the patient's eGFR: avoid / caution / normal + dose
   │
   ▼  ml/pipelines/combined_suggestion.py
final: renally-safe, ranked suggestion list with dose guidance + citation
```

## Why two layers
- **ML alone** can rank by what fits a patient, but has no notion of renal safety
  and could suggest a contraindicated drug.
- **Rules alone** know safety but cannot rank by clinical fit.
- **Combined**: the model proposes; the handbook removes unsafe drugs and adds
  dose guidance. The model never overrides safety — a handbook `avoid` is dropped
  regardless of ML score.

## Run
```bash
cd ml/pipelines
python combined_suggestion.py                                  # synthetic demo
python combined_suggestion.py --source mimic --db ../../backend/renal.db
```

## Output columns
- `ml_score` — prescribing-likelihood from the model (higher = better fit)
- `safety` — handbook verdict at the patient's eGFR: normal / caution / avoid / unknown
- `dose_guidance` — the handbook action for that eGFR band
- `reference` — citation (Renal Drug Handbook 5th ed.)

Drugs the handbook marks **avoid** are listed separately as removed, with the reason.

## Safety design
`handbook_safety.py` applies a per-drug hard avoid-threshold (`AVOID_BELOW`) as a
backstop independent of the free-text parsing, so a drug is never suggested below
its known renal cutoff even if the text parse is imperfect. `unknown` means the
drug isn't in the curated handbook subset or the band couldn't be read — treat as
"check the monograph", not as safe.

## Limitations
- Safety filter anchors on the three standard GFR bands (20-50 / 10-20 / <10);
  drug-specific bands are approximated to these.
- `unknown` rows need manual handbook lookup.
- ML ranking quality depends on the training data (synthetic = demo; real MIMIC
  = meaningful).
