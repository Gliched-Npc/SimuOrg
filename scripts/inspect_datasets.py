"""Quick script to dump column schemas of all 3 datasets."""
import pandas as pd, json, sys

files = {
    "MASTER": r"backend/data/SimuOrg_Master_Dataset.csv",
    "IBM_HR": r"C:\Users\LENOVO\Downloads\WA_Fn-UseC_-HR-Employee-Attrition (1).csv",
    "TRAIN": r"C:\Users\LENOVO\Downloads\train.csv\train.csv",
}

for name, path in files.items():
    try:
        df = pd.read_csv(path)
    except Exception as e:
        print(f"SKIP {name}: {e}")
        continue
    print(f"\n{'='*60}")
    print(f"  {name}  |  {len(df)} rows x {len(df.columns)} cols")
    print(f"{'='*60}")
    for c in df.columns:
        dt = str(df[c].dtype)
        nu = df[c].nunique()
        sample = df[c].dropna().unique()[:5].tolist()
        print(f"  {c:<35} {dt:<10} {nu:>4} uniques  ex: {sample}")
