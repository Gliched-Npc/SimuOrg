import pandas as pd

path = r"C:\Data Science\Week 4\IBM_HR_Analytics_Employee_Attrition_&_Performance_With_ManagerID.csv"
d = pd.read_csv(path)

print(f"Total: {len(d)} rows, {len(d.columns)} cols")
print()

print("=== ALL COLUMNS ===")
for c in d.columns:
    dt = str(d[c].dtype)
    nu = d[c].nunique()
    print(f"  {c} | {dt} | {nu} unique")

print()
print("=== CATEGORICAL (object) COLUMNS ===")
for c in d.select_dtypes(include="object").columns:
    print(f"  {c}: {d[c].unique().tolist()}")

print()
print("=== EmployeeID ===")
print(f"  range: {d['EmployeeID'].min()} - {d['EmployeeID'].max()}")
print(f"  unique: {d['EmployeeID'].nunique()}")

print()
print("=== ManagerID ===")
print(f"  range: {d['ManagerID'].min()} - {d['ManagerID'].max()}")
print(f"  unique: {d['ManagerID'].nunique()}")
mgr_in_emp = d["ManagerID"].isin(d["EmployeeID"]).sum()
print(f"  ManagerIDs that are valid EmployeeIDs: {mgr_in_emp}/{len(d)}")

# Compare with master dataset
print()
print("=== COMPARISON WITH MASTER ===")
master = pd.read_csv("backend/data/SimuOrg_Master_Dataset.csv", nrows=1)
master_cols = set(master.columns)
ibm_cols = set(d.columns)
print(f"  In this but NOT in Master: {ibm_cols - master_cols}")
print(f"  In Master but NOT in this: {master_cols - ibm_cols}")
print(f"  Common: {ibm_cols & master_cols}")
