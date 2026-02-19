# ml/attrition_model.py

import pandas as pd
import joblib
import os
from sqlmodel import Session, select
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from backend.database import engine
from backend.models import Employee

# These are the columns the model will learn from
FEATURES = [
    "job_satisfaction",
    "work_life_balance",
    "environment_satisfaction",
    "job_involvement",
    "monthly_income",
    "years_at_company",
    "total_working_years",
    "num_companies_worked",
    "job_level",
]

TARGET = "attrition"  # Yes / No


def load_data_from_db():
    with Session(engine) as session:
        employees = session.exec(select(Employee)).all()
    
    df = pd.DataFrame([e.model_dump() for e in employees])
    return df


def train_attrition_model():
    print("📊 Loading data from database...")
    df = load_data_from_db()
    # Convert target to binary
    df[TARGET] = df[TARGET].map({"Yes": 1, "No": 0})

    X = df[FEATURES]
    y = df[TARGET]

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Pipeline: RandomForest
    pipeline = Pipeline([
    ("model", RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42,
        class_weight="balanced"
    ))
])
    pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = pipeline.predict(X_test)
    print("\n📈 Attrition Model Performance:")
    print(classification_report(y_test, y_pred, target_names=["Stays", "Quits"]))

    # Dummy model to check the accuracy
    # from sklearn.dummy import DummyClassifier
    # dummy = DummyClassifier(strategy="most_frequent")
    # dummy.fit(X_train, y_train)
    # dummy_pred = dummy.predict(X_test)
    # print("\n🎲 Dummy Model (baseline):")
    # print(classification_report(y_test, dummy_pred, target_names=["Stays", "Quits"]))


    train_pred = pipeline.predict(X_train)
    print("\n🔍 Training Performance:")
    print(classification_report(y_train, train_pred, target_names=["Stays", "Quits"]))
    print("\n🔍 Test Performance:")
    print(classification_report(y_test, y_pred, target_names=["Stays", "Quits"]))

    from sklearn.metrics import accuracy_score
    train_accuracy = accuracy_score(y_train, pipeline.predict(X_train))
    test_accuracy  = accuracy_score(y_test, y_pred)

    print(f"\n📊 Accuracy Summary:")
    print(f"  Training Accuracy : {train_accuracy:.4f} ({train_accuracy*100:.2f}%)")
    print(f"  Test Accuracy     : {test_accuracy:.4f} ({test_accuracy*100:.2f}%)")
    print(f"  Overfitting Gap   : {(train_accuracy - test_accuracy)*100:.2f}%")

    # Save
    os.makedirs("backend/ml/exports", exist_ok=True)
    joblib.dump(pipeline, "backend/ml/exports/quit_probability.pkl")
    print("✅ Model saved to ml/exports/quit_probability.pkl")


if __name__ == "__main__":
    train_attrition_model()
# ```

# ---

# **What this does simply:**
# ```
# Database → load employees
#          → train logistic regression
#          → evaluate accuracy
#          → save frozen model to ml/exports/
# ```

# ---

# Run it with:
# ```
# python -m ml.attrition_model