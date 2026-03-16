import pandas as pd
import numpy as np
import os

def create_datasets():
    os.makedirs("test_datasets", exist_ok=True)
    
    # Base mandatory columns
    columns = [
        "EmployeeID", "ManagerID", "Department", "JobRole", "Age", "MonthlyIncome", 
        "JobLevel", "YearsAtCompany", "YearsInCurrentRole", "YearsSinceLastPromotion", 
        "YearsWithCurrManager", "DistanceFromHome", "NumCompaniesWorked", 
        "PercentSalaryHike", "TotalWorkingYears", "TrainingTimesLastYear", 
        "JobSatisfaction", "WorkLifeBalance", "EnvironmentSatisfaction", 
        "PerformanceRating", "JobInvolvement", "Attrition"
    ]

    depts = ["Sales", "Research & Development", "Human Resources"]
    roles = ["Sales Executive", "Research Scientist", "Laboratory Technician", "Manufacturing Director"]

    # 1. CLEAN DATASET (400 rows, healthy signals)
    data_clean = []
    for i in range(400):
        age = np.random.randint(22, 60)
        income = age * 200 + np.random.randint(2000, 5000)
        attrition = "No" if (income > 8000 or np.random.random() > 0.15) else "Yes"
        data_clean.append([
            i, i % 50 + 1000, np.random.choice(depts), np.random.choice(roles),
            age, income, np.random.randint(1, 6), np.random.randint(0, 20),
            np.random.randint(0, 10), np.random.randint(0, 10), np.random.randint(0, 10),
            np.random.randint(1, 30), np.random.randint(0, 8), np.random.randint(11, 25),
            np.random.randint(1, 40), np.random.randint(0, 6), np.random.randint(1, 5),
            np.random.randint(1, 5), np.random.randint(1, 5), 
            np.random.randint(1, 5), np.random.randint(1, 5), attrition
        ])
    pd.DataFrame(data_clean, columns=columns).to_csv("test_datasets/data_clean.csv", index=False)

    # 2. EXTREME ATTRITION (>40%)
    data_extreme = []
    for i in range(100):
        attrition = "Yes" if np.random.random() > 0.3 else "No"
        data_extreme.append([
            i, 1001, "Sales", "Sales Executive", 30, 5000, 1, 1, 1, 1, 1, 10, 1, 15, 5, 2, 3, 3, 3, 
            np.random.randint(1, 5), np.random.randint(1, 5), attrition
        ])
    pd.DataFrame(data_extreme, columns=columns).to_csv("test_datasets/data_extreme_attrition.csv", index=False)

    # 3. ZERO MATHEMATICAL SIGNAL (Randomized)
    data_random = []
    for i in range(200):
        attrition = "Yes" if np.random.random() > 0.5 else "No"
        data_random.append([
            i, 2000, np.random.choice(depts), np.random.choice(roles),
            np.random.randint(20, 60), np.random.randint(2000, 20000),
            np.random.randint(1, 6), np.random.randint(0, 20),
            np.random.randint(0, 10), np.random.randint(0, 10), np.random.randint(0, 10),
            np.random.randint(1, 30), np.random.randint(0, 8), np.random.randint(11, 25),
            np.random.randint(1, 40), np.random.randint(0, 6),
            3, 3, 3, # Zero variance in satisfaction
            3, 3, # Zero variance in performance/involvement
            attrition
        ])
    pd.DataFrame(data_random, columns=columns).to_csv("test_datasets/data_random_no_signal.csv", index=False)

    # 4. TINY DATASET (Only 15 rows)
    pd.DataFrame(data_clean[:15], columns=columns).to_csv("test_datasets/data_tiny.csv", index=False)

    # 5. NEGATIVE INCOME & INVALID JOBLEVELS
    data_bad_values = []
    for i in range(100):
        income = -100 if i < 10 else 5000
        level = 10 if i < 20 else 2
        data_bad_values.append([
            i, 1001, "Human Resources", "Research Scientist", 30, income, level, 1, 1, 1, 1, 10, 1, 15, 5, 2, 3, 3, 3, 
            3, 3, "No"
        ])
    pd.DataFrame(data_bad_values, columns=columns).to_csv("test_datasets/data_bad_values.csv", index=False)

    # 6. SPARSE / JUNK DATA (Many NaNs)
    data_junk = []
    for i in range(50):
        # 3 real rows, 47 junk rows
        if i < 3:
            data_junk.append([i, 1001, "Sales", "Executive", 30, 5000, 1, 1, 1, 1, 1, 10, 1, 15, 5, 2, 3, 3, 3, 3, 3, "No"])
        else:
            # Row with only ID and Age, rest NaNs
            row = [None] * len(columns)
            row[0] = i
            row[4] = 30
            data_junk.append(row)
    pd.DataFrame(data_junk, columns=columns).to_csv("test_datasets/data_sparse_trash.csv", index=False)

    # 7. MISSING FEATURE (One specific column is 90% empty)
    data_missing_col = []
    base_clean = pd.read_csv("test_datasets/data_clean.csv")
    col_idx = columns.index("YearsWithCurrManager")
    for i, row in base_clean.iterrows():
        new_row = list(row)
        if i > 40: # 90% missing for 400 rows
            new_row[col_idx] = None
        data_missing_col.append(new_row)
    pd.DataFrame(data_missing_col, columns=columns).to_csv("test_datasets/data_missing_feature.csv", index=False)

    print(f"Created 7 test datasets in 'test_datasets/' directory.")

if __name__ == "__main__":
    create_datasets()
