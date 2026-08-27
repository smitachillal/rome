import pandas as pd
import sqlite3
from pathlib import Path
# -----------------------------
# 1. File paths
# -----------------------------

# csv_file = ".\data\samples\prescriptions.csv"
# database_file = ".\backend\renal.db"

BASE_DIR = Path(__file__).resolve().parent.parent
# CSV path
csv_file = BASE_DIR / "data" / "samples" / "prescriptions.csv"

# SQLite database path
database_file = BASE_DIR / "backend" / "renal.db"

print("CSV:", csv_file)
print("Database:", database_file)

# -----------------------------
# 2. Load CSV
# -----------------------------
df = pd.read_csv(csv_file)

# -----------------------------
# 3. Select required columns
# -----------------------------
selected_columns = [
    "subject_id",
    "starttime",
    "stoptime",
    "drug_type",
    "drug",
    "prod_strength",
    "dose_val_rx",
    "dose_unit_rx",
    "form_unit_disp",
    "doses_per_24_hrs"
]

df_selected = df[selected_columns]

df_selected.insert(
    0,
    "id",
    range(1, len(df) + 1)
)

#print(df_selected)
# -----------------------------
# 4. Connect to SQLite database
# -----------------------------
conn = sqlite3.connect(database_file)

# -----------------------------
# 5. Save into a new table
# -----------------------------
df_selected.to_sql(
    "prescriptions",
    conn,
    if_exists="fail",
    index=False
)

# Verify table
cursor = conn.cursor()

cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
""")

print("Tables:", cursor.fetchall())

conn.commit()
# -----------------------------
# 6. Close connection
# -----------------------------
conn.close()

print("Data successfully saved to SQLite.")