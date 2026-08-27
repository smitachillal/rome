#!/usr/bin/env python3
"""One-command loader for the MIMIC-IV Clinical Database Demo (v2.2).

Takes the downloaded zip (or an already-extracted folder), finds the `hosp`
directory wherever it sits, checks the files we need are present, and imports
the data into the app's SQLite database — deriving eGFR, CrCl, AKI stage and
CKD stage on the way in.

The demo is OPEN ACCESS (100 patients, no credentialing) and its CSVs are
gzipped; pandas reads .csv.gz directly, so nothing needs unzipping by hand.

Usage (from the repo root):
    python scripts/load_mimic_demo.py --zip ~/Downloads/mimic-iv-clinical-database-demo-2.2.zip
    python scripts/load_mimic_demo.py --dir  ~/data/mimic-iv-clinical-database-demo-2.2
    python scripts/load_mimic_demo.py --zip <path> --limit 50     # fewer patients
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_EXTRACT = REPO / "ml" / "data" / "mimic-demo"

# The importer lives at <backend>/app/services/import_csv.py. Different projects
# lay this out differently, so locate it rather than assuming a fixed path.
IMPORTER_REL = Path("app") / "services" / "import_csv.py"


def find_backend(explicit: str | None = None) -> Path | None:
    """Return the directory that contains `app/services/import_csv.py`."""
    if explicit:
        cand = Path(explicit).expanduser().resolve()
        return cand if (cand / IMPORTER_REL).exists() else None

    candidates = [
        REPO / "backend",          # standard layout
        REPO,                      # app/ sits at the repo root
        REPO / "src" / "backend",
        REPO / "server",
        REPO / "api",
        Path.cwd(), Path.cwd() / "backend",
    ]
    for c in candidates:
        if (c / IMPORTER_REL).exists():
            return c.resolve()

    # last resort: shallow search under the repo (skip heavy folders)
    skip = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
    for hit in REPO.rglob(str(IMPORTER_REL)):
        if not any(part in skip for part in hit.parts):
            return hit.parents[2].resolve()
    return None

REQUIRED = ["patients", "labevents", "prescriptions"]
OPTIONAL = ["omr"]          # omr -> weight -> CrCl


def find_hosp(root: Path) -> Path | None:
    """Locate the `hosp` directory anywhere under root."""
    if (root / "hosp").is_dir():
        return root / "hosp"
    for p in root.rglob("hosp"):
        if p.is_dir():
            return p
    # some distributions flatten the files
    if any(p.is_file() for p in root.glob("labevents.csv*")):
        return root
    return None


def check_files(hosp: Path) -> tuple[list[str], list[str], list[str]]:
    """Return (present, missing, folder_traps).

    `folder_traps` are names like 'patients.csv' that exist as DIRECTORIES —
    a common result of extracting with a tool that makes a folder per file.
    Reading one raises PermissionError on Windows / IsADirectoryError on Linux.
    """
    present, missing, traps = [], [], []
    for stem in REQUIRED + OPTIONAL:
        hits = list(hosp.glob(stem + ".csv*"))
        files = [h for h in hits if h.is_file()]
        if files:
            present.append(stem)
        else:
            if any(h.is_dir() for h in hits):
                traps.append(stem)
            missing.append(stem)
    return present, missing, traps


def main(a: argparse.Namespace) -> int:
    # ---- 1. get an extracted folder ----
    if a.zip:
        zpath = Path(a.zip).expanduser()
        if not zpath.exists():
            print(f"ERROR: zip not found: {zpath}")
            return 1
        dest = Path(a.extract_to).expanduser() if a.extract_to else DEFAULT_EXTRACT
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Extracting {zpath.name} -> {dest} ...")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(dest)
        root = dest
    else:
        root = Path(a.dir).expanduser()
        if not root.exists():
            print(f"ERROR: folder not found: {root}")
            return 1

    # ---- 2. locate hosp ----
    hosp = find_hosp(root)
    if hosp is None:
        print(f"ERROR: could not find a 'hosp' directory under {root}")
        print("       Expected .../mimic-iv-clinical-database-demo-2.2/hosp/")
        return 1
    print(f"Found hosp directory: {hosp}")

    # ---- 3. verify the files we need ----
    present, missing, traps = check_files(hosp)
    for stem in REQUIRED:
        mark = "OK " if stem in present else "MISSING"
        print(f"  [{mark:7s}] {stem}.csv[.gz]")
    for stem in OPTIONAL:
        mark = "OK " if stem in present else "absent"
        note = "" if stem in present else "   (no weight -> CrCl will be null)"
        print(f"  [{mark:7s}] {stem}.csv[.gz]{note}")

    if traps:
        print(f"\nERROR: these exist as FOLDERS, not files: "
              f"{', '.join(t + '.csv' for t in traps)}")
        print("       Your archive was extracted with a tool that created a")
        print("       directory per file. Fix by re-extracting the original zip")
        print("       (Windows: right-click > Extract All), or point --dir at the")
        print("       folder that actually contains the .csv/.csv.gz files.")
        return 1

    hard_missing = [s for s in REQUIRED if s in missing]
    if hard_missing:
        print(f"\nERROR: required files missing: {', '.join(hard_missing)}")
        return 1

    # ---- 4. import (reuses the app's importer, so all parameters get derived) ----
    backend = find_backend(a.backend)
    if backend is None:
        print("\nERROR: could not locate the backend package.")
        print(f"       Looked for: <backend>/{IMPORTER_REL}")
        print(f"       Repo root detected as: {REPO}")
        print("\n       Checked these locations:")
        for c in [REPO / "backend", REPO, REPO / "src" / "backend",
                  REPO / "server", REPO / "api", Path.cwd()]:
            print(f"         - {c}")
        print("\n       Fix it one of two ways:")
        print("         1) point at it explicitly:")
        print("            python scripts/load_mimic_demo.py --zip <zip> --backend path/to/backend")
        print("         2) or import directly from the backend folder:")
        print("            cd <backend>")
        print("            python -m app.services.import_csv --mode mimic --path "
              f"{hosp}")
        return 1

    print(f"Using backend: {backend}")
    sys.path.insert(0, str(backend))
    os.chdir(backend)                      # so sqlite:///./renal.db lands beside the app
    try:
        from app.services.import_csv import import_mimic
    except ModuleNotFoundError as e:
        print(f"\nERROR: found {backend} but could not import the app package: {e}")
        print("       Is the backend's virtualenv active, and are deps installed?")
        print(f"       Try: cd {backend} && pip install -r requirements.txt")
        return 1

    print("\nImporting (deriving eGFR, CrCl, AKI stage, CKD stage) ...")
    try:
        stats = import_mimic(str(hosp), a.limit)
    except PermissionError as e:
        print(f"\nERROR: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return 1
    print("\nImport complete:")
    for k, v in stats.items():
        print(f"  {k:16s} {v}")
    print(f"\nDatabase written to: {backend / 'renal.db'}")

    if stats.get("crcl_computed", 0) == 0:
        print("\nNOTE: no CrCl computed — no weight found in OMR for these patients.")
        print("      CrCl-dosed drugs will fall back to eGFR.")

    print("\nNext steps:")
    print("  python ml/pipelines/train_and_save.py --db backend/renal.db   # retrain")
    print("  cd backend && uvicorn app.main:app --reload                   # run the app")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", help="path to mimic-iv-clinical-database-demo-2.2.zip")
    src.add_argument("--dir", help="path to an already-extracted demo folder")
    ap.add_argument("--extract-to", help="where to extract (default ml/data/mimic-demo)")
    ap.add_argument("--limit", type=int, default=None, help="cap number of patients")
    ap.add_argument("--backend", help="path to the backend folder containing app/ "
                                     "(only needed if auto-detection fails)")
    sys.exit(main(ap.parse_args()))
