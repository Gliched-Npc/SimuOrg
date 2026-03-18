# SimuOrg Project: Deep-Level File Documentation

This report provides a comprehensive breakdown of the `SimuOrg` codebase, detailing the purpose and internal logic of each component.

## Root Directory

| File | Purpose | Deep-Level Description |
| :--- | :--- | :--- |
| [main.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/main.py) | Backend Entry Point | Initializes the FastAPI application, sets up CORS middleware, and includes all API routers (`sim_routes`, `upload_routes`, `ml_routes`). It also triggers the database initialization on startup. |
| [database.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/database.py) | Database Connection | Handles the SQLAlchemy/SQLModel engine creation using the database URL from environment variables. |
| [models.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/models.py) | Data Models | Defines the SQLModel schemas for [Employee](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/simulation/agent.py#75-222), `SimulationResult`, and other database entities. It acts as the "Source of Truth" for the data structure. |
| [schema.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/schema.py) | Data Validation | Contains Pydantic-style schemas used for clarifying API request/response structures and data cleaning logic. |
| [config.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/config.py) | Configuration Manager | Loads environment variables (like DB credentials, API keys) and provides a central configuration object for the application. |
| [auth.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/auth.py) | Authentication Logic | (Stub or Minimal) Handles user authentication and session management if applicable. |
| [upload.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/upload.py) | Data Ingestion Processor | Contains the logic for parsing uploaded CSV files, cleaning the data (normalizing columns, handling nulls), and ingesting it into the database. |
| [quality_checker.py](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/quality_checker.py) | Data Diagnostics | Performs a pre-cleaning mathematical scan to detect issues like extreme attrition rates, small sample sizes, or zero-variance features. It returns actionable suggestions to the user. |
| [docker-compose.yml](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/docker-compose.yml) | Container Orchestration | Defines the services (Backend, Frontend, PostgreSQL) for running the entire stack in containers. |
| [requirements.txt](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/requirements.txt) | Python Dependencies | Lists all necessary Python packages (FastAPI, SQLModel, XGBoost, SHAP, etc.). |

---

## Backend: Machine Learning (`backend/ml/`)

This directory contains the brains of the project—predictive models and calibration logic.

| File | Purpose | Deep-Level Description |
| :--- | :--- | :--- |
| `attrition_model.py` | Attrition Predictor | Trains an `XGBClassifier` to predict employee quit probability. It uses `scale_pos_weight` for imbalance handling and `IsotonicRegression` for probability calibration. Includes a "CEO-optimized" threshold tuner. |
| `calibration.py` | Simulation Tuning | Fits behavioral parameters (stress gain, recovery rates) by running iterative simulations and using binary search to match historical attrition rates. |
| `burnout_estimator.py` | Burnout Threshold Logic | Calculates an employee's maximum stress tolerance based on their `JobLevel` and `TotalWorkingYears`. |
| `productivity_decay.py` | Productivity Algorithms | Defines how stress, fatigue, and job satisfaction non-linearly impact an employee's daily output. |
| `train.py` | Training Orchestrator | A convenience script/function to trigger the full model training and evaluation pipeline. |

---

## Backend: Simulation Engine (`backend/simulation/`)

This directory handles the "Agent-Based Modeling" part of the platform.

| File | Purpose | Deep-Level Description |
| :--- | :--- | :--- |
| `agent.py` | Employee Surrogate | Defines the `EmployeeAgent` class. Each agent is an autonomous entity that carries its own state (stress, fatigue, motivation) and can "decide" to quit based on the ML model's output. |
| `behavior_engine.py` | Behavioral Physics | The core logic for updating agent states. It handles peer influence (neighbor stress), stress accumulation, and "attrition shockwaves" (the impact on team morale when someone leaves). |
| `time_engine.py` | Month-by-Month Loop | Orchestrates the simulation time flow. It manages departures, hiring replacements (with culture inheritance), and aggregating monthly metrics. |
| `org_graph.py` | Organizational Topology | Builds a NetworkX graph representing the company's hierarchy and social edges. This graph is used to transmit stress and influence between employees. |
| `monte_carlo.py` | Statistical Stability | Runs multiple simulation passes (e.g., 50-100 runs) and aggregates results to provide means, standard deviations, and "Stability" flags for leadership. |
| `policies.py` | Scenario Definitions | Stores the configurations for different intervention scenarios like "Flexible Work," "Promotion Freeze," or "KPI Pressure." |

---

## Backend: API Layer (`backend/api/`)

| File | Purpose | Deep-Level Description |
| :--- | :--- | :--- |
| `ml_routes.py` | ML & XAI Endpoints | Provides endpoints for model metrics, SHAP-based individual explanations (`/explain/{id}`), and global feature importance. |
| `sim_routes.py` | Simulation Controls | Handles starting simulations, fetching results, and providing "Baseline" vs "Scenario" comparisons. |
| `upload_routes.py` | Data Upload Interface | Manage the multi-step upload flow (Upload → Quality Check → Review → Ingest). |

---

## Frontend: React Application (`frontend/src/`)

| Directory/File | Purpose | Description |
| :--- | :--- | :--- |
| `App.jsx` | Main Entry & Routing | Sets up the main layout, global styles, and client-side routing. |
| `pages/Dashboard.jsx` | Overview Hub | Shows high-level health metrics, current headcount, and quick-links to simulation controls. |
| `pages/UploadData.jsx` | Data Ingestion UI | A step-wise wizard for uploading HR data, displaying the quality checker results, and confirming ingestion. |
| `pages/SimulationResults.jsx` | Visualization Page | Displays Monte Carlo trends, attrition curves, and executive narratives using interactive charts. |
| `components/ChartPanel.jsx` | Reusable Visuals | Wrapper for Recharts/D3 components to display simulation trends. |
| `components/SimulationCard.jsx` | Scenario Trigger | A card-based UI for selecting and launching different simulation policies. |
| `services/api.js` | Backend Bridge | Standardized Axios instance for communicating with the FastAPI backend. |

---

## Summary of the "Deep Logic"
SimuOrg is unique because its **predictive power (the ML model)** is coupled with a **dynamic physics engine (the simulation)**. 
1. **ML Model** identifies *who* is likely to quit based on static snapshots.
2. **Behavior Engine** simulates *when* they quit after being subjected to new policies (e.g., more workload).
3. **Calibration Logic** ensures that the "fictional" simulation results match real-world historical patterns before projecting into the future.
