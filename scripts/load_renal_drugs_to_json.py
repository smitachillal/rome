import pandas as pd

#df = pd.read_csv("renal_drug_handbook_decision_tree_dataset.csv")
df = pd.read_csv("./../ml/data/renal_drug_handbook_decision_tree_dataset.csv")

df.to_json(
    "drugs.json",
    orient="records",
    indent=4
)

print("JSON created successfully!")