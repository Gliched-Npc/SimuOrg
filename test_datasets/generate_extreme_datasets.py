import os
import random

import numpy as np
import pandas as pd


def generate_extreme_dataset(filename="data_burnout_central.csv", num_samples=1000):
    np.random.seed(42)
    random.seed(42)

    data = []

    for i in range(1, num_samples + 1):
        # High burnout, high stress, high attrition profile
        age = np.random.randint(22, 60)

        # Generally low satisfaction and WLB
        job_sat = np.random.choice([1, 2, 3, 4], p=[0.5, 0.3, 0.15, 0.05])
        wlb = np.random.choice([1, 2, 3, 4], p=[0.6, 0.25, 0.1, 0.05])
        env_sat = np.random.choice([1, 2, 3, 4], p=[0.4, 0.3, 0.2, 0.1])

        # Long hours, high overtime
        overtime = np.random.choice(["Yes", "No"], p=[0.7, 0.3])

        job_level = np.random.choice([1, 2, 3, 4, 5], p=[0.4, 0.3, 0.2, 0.08, 0.02])
        monthly_income = 3000 * job_level + np.random.randint(1000, 3000)

        # High likelihood of attrition
        attrition_prob = 0.0
        if job_sat <= 2:
            attrition_prob += 0.3
        if wlb <= 2:
            attrition_prob += 0.3
        if overtime == "Yes":
            attrition_prob += 0.2
        if env_sat <= 2:
            attrition_prob += 0.1

        # Ensure ~50-60% overall attrition
        attrition = "Yes" if np.random.rand() < attrition_prob else "No"

        years_worked = np.random.randint(max(1, age - 22), max(age - 18, 2))
        years_at_company = np.random.randint(0, min(10, years_worked + 1))

        row = {
            "Age": age,
            "Attrition": attrition,
            "BusinessTravel": "Travel_Frequently",
            "Department": "Research & Development" if np.random.rand() < 0.5 else "Sales",
            "DistanceFromHome": np.random.randint(5, 30),
            "Education": np.random.randint(1, 5),
            "EducationField": "Life Sciences",
            "EmployeeCount": 1,
            "EmployeeNumber": i,
            "EnvironmentSatisfaction": env_sat,
            "Gender": np.random.choice(["Male", "Female"]),
            "HourlyRate": np.random.randint(50, 100),
            "JobInvolvement": np.random.choice([1, 2, 3, 4]),
            "JobLevel": job_level,
            "JobRole": "Laboratory Technician",
            "JobSatisfaction": job_sat,
            "ManagerID": np.random.randint(1, i) if i > 1 else None,
            "MaritalStatus": "Single",
            "MonthlyIncome": monthly_income,
            "MonthlyRate": np.random.randint(10000, 20000),
            "NumCompaniesWorked": np.random.randint(1, 5),
            "Over18": "Y",
            "OverTime": overtime,
            "PercentSalaryHike": np.random.randint(11, 25),
            "PerformanceRating": 3 if np.random.rand() < 0.8 else 4,
            "RelationshipSatisfaction": np.random.choice([1, 2, 3, 4]),
            "StandardHours": 80,
            "StockOptionLevel": np.random.choice([0, 1, 2]),
            "TotalWorkingYears": years_worked,
            "TrainingTimesLastYear": np.random.randint(0, 6),
            "WorkLifeBalance": wlb,
            "YearsAtCompany": years_at_company,
            "YearsInCurrentRole": int(years_at_company * 0.8),
            "YearsSinceLastPromotion": int(years_at_company * 0.3),
            "YearsWithCurrManager": int(years_at_company * 0.5),
        }
        data.append(row)

    df = pd.DataFrame(data)

    # Save burnout
    out_path = os.path.join(os.path.dirname(__file__), filename)
    df.to_csv(out_path, index=False)
    print(f"Generated {filename} with Attrition Rate: {(df['Attrition'] == 'Yes').mean():.1%}")


def generate_chill_dataset(filename="data_chill_utopia.csv", num_samples=1000):
    np.random.seed(99)
    random.seed(99)

    data = []
    for i in range(1, num_samples + 1):
        age = np.random.randint(25, 60)

        # High satisfaction and WLB
        job_sat = np.random.choice([1, 2, 3, 4], p=[0.02, 0.08, 0.4, 0.5])
        wlb = np.random.choice([1, 2, 3, 4], p=[0.01, 0.04, 0.35, 0.6])
        env_sat = np.random.choice([1, 2, 3, 4], p=[0.05, 0.1, 0.4, 0.45])

        overtime = np.random.choice(["Yes", "No"], p=[0.05, 0.95])

        job_level = np.random.choice([1, 2, 3, 4, 5], p=[0.2, 0.3, 0.3, 0.15, 0.05])
        monthly_income = 5000 * job_level + np.random.randint(2000, 5000)

        # Low likelihood of attrition
        attrition_prob = 0.02
        if job_sat <= 2:
            attrition_prob += 0.1
        if wlb <= 2:
            attrition_prob += 0.1
        if overtime == "Yes":
            attrition_prob += 0.05

        attrition = "Yes" if np.random.rand() < attrition_prob else "No"

        years_worked = np.random.randint(max(1, age - 22), max(age - 18, 2))
        years_at_company = np.random.randint(min(years_worked, 3), years_worked + 1)

        row = {
            "Age": age,
            "Attrition": attrition,
            "BusinessTravel": "Travel_Rarely",
            "Department": "Research & Development" if np.random.rand() < 0.7 else "Sales",
            "DistanceFromHome": np.random.randint(1, 10),
            "Education": np.random.randint(3, 5),
            "EducationField": "Medical",
            "EmployeeCount": 1,
            "EmployeeNumber": i,
            "EnvironmentSatisfaction": env_sat,
            "Gender": np.random.choice(["Male", "Female"]),
            "HourlyRate": np.random.randint(50, 100),
            "JobInvolvement": np.random.choice([3, 4]),
            "JobLevel": job_level,
            "JobRole": "Research Director",
            "JobSatisfaction": job_sat,
            "ManagerID": np.random.randint(1, i) if i > 1 else None,
            "MaritalStatus": "Married",
            "MonthlyIncome": monthly_income,
            "MonthlyRate": np.random.randint(10000, 20000),
            "NumCompaniesWorked": np.random.randint(1, 3),
            "Over18": "Y",
            "OverTime": overtime,
            "PercentSalaryHike": np.random.randint(15, 25),
            "PerformanceRating": 3 if np.random.rand() < 0.5 else 4,
            "RelationshipSatisfaction": np.random.choice([3, 4]),
            "StandardHours": 80,
            "StockOptionLevel": np.random.choice([1, 2, 3]),
            "TotalWorkingYears": years_worked,
            "TrainingTimesLastYear": np.random.randint(2, 6),
            "WorkLifeBalance": wlb,
            "YearsAtCompany": years_at_company,
            "YearsInCurrentRole": int(years_at_company * 0.8),
            "YearsSinceLastPromotion": int(years_at_company * 0.4),
            "YearsWithCurrManager": int(years_at_company * 0.7),
        }
        data.append(row)

    df = pd.DataFrame(data)

    out_path = os.path.join(os.path.dirname(__file__), filename)
    df.to_csv(out_path, index=False)
    print(f"Generated {filename} with Attrition Rate: {(df['Attrition'] == 'Yes').mean():.1%}")


if __name__ == "__main__":
    generate_extreme_dataset()
    generate_chill_dataset()
