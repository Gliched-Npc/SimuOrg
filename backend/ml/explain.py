import joblib
import pandas as pd
import shap
from sqlmodel import Session, select
from backend.database import engine
from backend.models import Employee
from backend.ml.attrition_model import engineer_features

def explain_employee(employee_id: int):
    # Load model, threshold, and feature list
    try:
        model_data = joblib.load("backend/ml/exports/quit_probability.pkl")
    except FileNotFoundError:
        return {"error": "Model not found. Please train the model first."}
        
    model = model_data["model"]
    features = model_data["features"]
    
    # Load employee from database
    with Session(engine) as session:
        employee = session.exec(select(Employee).where(Employee.employee_id == employee_id)).first()
        
    if not employee:
        return {"error": f"Employee with ID {employee_id} not found."}
        
    # Convert to DataFrame and engineer features
    df = pd.DataFrame([employee.model_dump()])
    df = engineer_features(df)
    
    # Filter only the features used by the model
    # Fill missing optional features with 0 (which is the default in the app)
    for f in features:
        if f not in df.columns:
            df[f] = 0
            
    X = df[features]
    
    # Initialize SHAP explainer
    # TreeExplainer is ideal for XGBoost
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    
    # shap_values is a list of arrays if multi-class, but for binary classification with XGBoost 
    # and depending on the objective, it might be a single array.
    # We will compute the base value and feature contributions.
    
    # The SHAP values are usually in log-odds (margin). We can convert them to probability if needed,
    # but for explaining *factors*, the log-odds impact is sufficient to rank them.
    
    row_shap = shap_values[0] if isinstance(shap_values, list) else shap_values[0]
    
    # Combine feature names, their actual values, and their SHAP contributions
    factors = []
    for i, feature in enumerate(features):
        factors.append({
            "feature": feature,
            "value": float(X.iloc[0][feature]),
            "contribution": float(row_shap[i])
        })
        
    # Sort by absolute contribution to find the most impactful features
    factors.sort(key=lambda x: abs(x["contribution"]), reverse=True)
    
    # Separate into push (makes them want to quit) and pull (makes them want to stay)
    push_factors = [f for f in factors if f["contribution"] > 0]
    pull_factors = [f for f in factors if f["contribution"] < 0]
    
    # Calculate base probability
    probability = model.predict_proba(X)[0][1]
    
    return {
        "employee_id": employee_id,
        "quit_probability": float(probability),
        "top_push_factors": push_factors[:3], # Top 3 reasons they might quit
        "top_pull_factors": pull_factors[:3], # Top 3 reasons they stay
        "all_factors": factors
    }
