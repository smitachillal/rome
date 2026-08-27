# Drug interactions — graphical checker (DDInter-style)

Recreates the DDInter interaction checker inside the app: a network graph of drugs
(nodes) and interactions (severity-coloured edges), plus detail cards with severity
badge, interaction text, and management text.

## Data sources (checked in order)
1. **DDInter dataset** — if loaded into `interactions.db` (see loader below).
2. **Curated renal set** — built-in, works out of the box, covers the
   renal-relevant pairs (anticoagulant combos, ACE+K-sparing, nephrotoxic combos).

Severity grades match DDInter: **Major / Moderate / Minor / Unknown**.

## Loading DDInter data (your Option-1 refresh mechanism)
DDInter is open-access and publishes downloadable CSVs. Download them from
https://ddinter.scbdd.com/ (Download tab), then:
```bash
python scripts/load_ddinter.py --dir path/to/ddinter_csvs --out backend/interactions.db
```
Re-run whenever you want to refresh — updating is one command, not manual entry.
The app auto-uses `interactions.db` if present (path via `INTERACTIONS_DB`).

## API + UI
- `GET /api/patients/{id}/interactions` → nodes, edges, pairs, severity counts.
- `frontend/src/components/InteractionGraph.jsx` → SVG network graph + detail cards.

## Safety
"Unknown" = no record in this source, NOT proof of safety. DDInter's own terms note
absence from the database does not prove no interaction exists. This is shown in the
UI footer and must be stated in the dissertation.

## Note on live APIs (why local, not live)
The free RxNav drug-drug interaction API was discontinued in Jan 2024, and DrugBank's
API is commercial. So a local, refreshable DDInter copy is the correct free approach —
it also keeps patient data on-device (important for the MIMIC data-use agreement).

## Getting only renal-relevant interactions from DDInter

DDInter splits downloads by ATC drug CLASS (A, B, D, H, L, P, R, V) — there is NO
single "renal" file, and "R" is Respiratory, not Renal. Renal-relevant drugs are
spread across several class files. For this project's drug list you mainly need:
- **code_A** (alimentary/metabolism): metformin, sitagliptin, allopurinol
- **code_B** (blood): apixaban, rivaroxaban, dabigatran, enoxaparin, warfarin
- (cardiovascular drugs like ACE inhibitors/digoxin/spironolactone — check the site
  for a code_C file; the download page listing may vary)

Download the CSVs from https://ddinter.scbdd.com/download/, then extract only the
renal-relevant pairs:
```bash
python scripts/filter_renal_ddinter.py --dir path/to/ddinter_csvs --out backend/interactions.db
```
This keeps only pairs where at least one drug is in `RENAL_DRUGS` (editable in the
script) and writes them to the app's interaction DB. Simplest: download all eight
(~13MB total) and let the filter pick the relevant subset.

Note: the bulk CSVs carry drug pairs + severity Level; full mechanism/management
text is shown per-pair on the website. The curated fallback set supplies text for
the key renal pairs so the cards are populated in the demo.
