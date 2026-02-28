# SimuOrg Backend Architecture & Working Documentation

This document explains the flow of the SimuOrg backend, breaking down the application into five core stages: Foundation, Data Ingestion, Machine Learning, the Simulation Engine, and API Orchestration. 

---

## 1. The Foundation & Entry Point
This layer holds the application together, handling the web server entry point and the database connection layer.

### `backend/main.py`
This is the entry point of the backend. It initializes the FastAPI application.
*   **`app` initialization:** Creates the FastAPI instance, setting up CORS middleware to allow the frontend to communicate with the backend.
*   **`include_router`:** Mounts the various API routers (`upload_routes`, `ml_routes`, `sim_routes`) so that the endpoints are accessible.
*   **Startup Event (`init_db`)**: Ensures the database tables are created when the server starts.

### `backend/database.py`
This file configures the connection to the database.
*   **`engine`:** Creates the SQLAlchemy engine connected to an SQLite database (`simuorg.db`).
*   **`init_db()`:** A function that creates all database tables defined by the SQLModel metadata.

### `backend/models.py`
This file defines the data schema for the database.
*   **`Employee` (SQLModel):** Defines the database table schema for an employee. It maps every column from the CSV dataset (like `age`, `job_role`, `monthly_income`) to a database column. It acts as both the Pydantic validation model and the SQLAlchemy ORM model.

---

## 2. Data Ingestion & Preprocessing
This stage handles receiving generic HR CSV data and cleaning it into a standardized format before saving it to the database.

### `backend/api/upload_routes.py`
The API layer for data ingestion.
*   **`upload_dataset(file)`:** 
    *   Receives the CSV file from the user.
    *   Calls `normalize_dataframe` to standardize the incoming data.
    *   Checks for missing required columns.
    *   Calls `build_schema_report` to generate a summary of the data quality.
    *   Calls `clean_dataframe` and `ingest_from_dataframe` to save the data to the DB.
    *   Triggers the ML training and calibration pipelines automatically after successful ingestion.

### `backend/schema.py`
A critical utility file that acts as a translation layer between messy, real-world HR data and our strict database schema.
*   **`normalize_columns(df)`:** Uses a fuzzy-matching dictionary (`COLUMN_ALIASES`) to map varying column names (like "Salary" or "Monthly_Income") to our canonical name (`MonthlyIncome`).
*   **`derive_missing_columns(df)`:** Guesses or derives missing columns based on other data (e.g. deriving `YearsSinceLastPromotion` from `NumberOfPromotions`).
*   **`encode_satisfaction_scores(df)`:** Converts text-based ratings ("Low", "High") into numeric 1-4 scales.
*   **`normalize_attrition(df)`:** Converts various attrition flags ("Left", "1", "True") into standardized "Yes"/"No" values.
*   **`encode_overtime(df)` / `encode_business_travel(df)`:** Encodes these specific columns into machine-readable numeric/ordinal values.
*   **`apply_optional_defaults(df)`:** Automatically fills in missing optional columns with sensible defaults (like Age=35).
*   **`build_schema_report(...)`:** Generates a CEO-friendly JSON report detailing which columns were found, which were missing (and defaulted), and which high-value columns (like `OverTime`) are missing.
*   **`normalize_dataframe(df)`:** A master pipeline function that calls all the above functions in sequence.

### `backend/upload.py`
The validation and database execution layer.
*   **`clean_dataframe(df)`:** Removes exact duplicate rows and enforces required data types (e.g., ensuring `EmployeeID` is not null).
*   **`validate_data_quality(df)`:** Checks for logical inconsistencies in the data (like employees younger than 18 or earning negative salaries) and generates warnings.
*   **`ingest_from_dataframe(df)`:** Opens a database session, clears the old `Employee` table, and efficiently bulk-inserts the newly cleaned dataset into the database.

---

## 3. The Machine Learning Pipeline
Once the data is clean and in the database, the system learns from historical patterns to predict who will quit and why.

### `backend/ml/attrition_model.py`
Trains the core predictive model.
*   **`engineer_features(df)`:** Creates new synthetic features (like `career_velocity`, `loyalty_factor`, `financial_stress`) from the raw data to give the model better predictive signals.
*   **`train_attrition_model()`:** 
    *   Loads all employees from the database.
    *   Trains an XGBoost Classifier on the engineered features to predict the `attrition` column.
    *   Saves the trained model to disk (`quit_probability.pkl`) using `joblib`.

### `backend/ml/calibration.py`
Grounds the ML model strictly in reality.
*   **`calibrate()`:** 
    *   Loads the trained model and predicts the quit probability for *every* employee currently in the database.
    *   Calculates the company's historical natural attrition rate based on the dataset.
    *   Dynamically calculates behavioral baseline numbers (`stress_gain_rate`, `recovery_rate`, `shockwave_stress_factor`) based on the company's average job satisfaction, work-life balance, and loyalty.
    *   Saves these baseline parameters to `calibration.json` to be used by the Simulation Engine.

### `backend/ml/burnout_estimator.py`
A secondary analytical model.
*   **`train_burnout_estimator()`:** A placeholder/utility for training a secondary model (currently handles simple distributions).
*   **`burnout_threshold(job_level, total_working_years)`:** A heuristic function that calculates at what stress percentage (0.0 to 1.0) a specific employee will "burn out" and lose productivity. Senior employees with more experience typically have higher thresholds.

### `backend/ml/explain.py`
The Explainable AI (XAI) engine.
*   **`explain_prediction(employee_id)`:** Uses the SHAP (SHapley Additive exPlanations) library to break down a specific employee's quit probability. It calculates exactly which features (e.g., low salary, high overtime) pushed their quit probability up, and which features (e.g., high job satisfaction) pushed it down.

### `backend/api/ml_routes.py`
The API layer for Machine Learning insights.
*   **`explain_employee(employee_id)`:** An endpoint that calls `explain_prediction` and returns the top risk factors and retention drivers for a specific employee.
*   **`get_feature_importance()`:** An endpoint that returns the global feature importance of the trained XGBoost model (i.e., which columns matter most across the entire company).

---

## 4. The Simulation Engine (The Core)
This is the core of SimuOrg. It turns static rows of data into a dynamic, time-series Monte Carlo simulation of human behavior.

### The Pieces (State)
*   **`backend/simulation/agent.py`:** 
    *   **`EmployeeAgent`:** A dynamic wrapper class around a static `Employee` database record. It initializes psychological states (`stress`=0.1, `motivation`=0.75, `fatigue`=0.0) and holds methods to update productivity and retrieve ML features.
*   **`backend/simulation/org_graph.py`:** 
    *   **`build_org_graph(agents)`:** Uses the NetworkX library to build a directed graph (a tree) out of the agents based on their `ManagerID`s. This determines who influences whom.

### The Rules (Updates)
*   **`backend/simulation/behavior_engine.py`:**
    *   **`compute_neighbor_influence(agent, G)`:** Looks at an agent's manager and peers in the org graph and calculates how much stress is bleeding over from them.
    *   **`update_agent_state(agent, ...)`:** The psychological core. Over one "month", it: increases stress based on workload and neighbor stress, applies recovery based on work-life balance, decays motivation if stress is high, drops productivity if the agent hits their burnout limit, and recalculates their Job Satisfaction.
    *   **`apply_attrition_shockwave(agent, G, ...)`:** If an agent quits, this function immediately spikes the stress and drops the loyalty of their direct neighbors in the org graph (Turnover Contagion).
*   **`backend/simulation/policies.py`:**
    *   **`SimulationConfig` / `POLICIES`:** Defines HR policies (like 'KPI Pressure' or '4-Day Work Week'). These policies alter mathematical multipliers (e.g., `workload_multiplier=1.2` or `motivation_decay_rate`).

### The Loop (Time Engine)
*   **`backend/simulation/time_engine.py`:**
    *   **`run_simulation(config, ...)`:** The main event loop. For $N$ months, it:
        1. Updates all agent states (`update_agent_state`).
        2. Processes forced layoffs (if any).
        3. Runs the ML model `predict_proba` on every agent to check if they voluntarily quit this month based on their new dynamic stress/satisfaction levels.
        4. Applies shockwaves to the peers of anyone who left.
        5. Hires "clones" to replace departed employees (resetting their tenure to 0).
        6. Logs the average metrics (stress, productivity) for the month.

### The Aggregator (Monte Carlo)
*   **`backend/simulation/monte_carlo.py`:**
    *   **`run_monte_carlo(config, runs)`:** Because the `time_engine` uses randomness (an employee with a 15% quit probability might quit in run 1 but stay in run 2), this script runs the `time_engine` in $X$ parallel universes (e.g., 50 runs) and aggregates the results to find the average expected outcome, along with the worst-case and best-case bounds.

---

## 5. API Execution & Orchestration
This layer handles the triggering of the simulation from the frontend.

### `backend/api/sim_routes.py`
*   **`run_simulation_endpoint` (`/api/sim/run`):** Takes a single policy request, ensures the database and model exist, and triggers `run_monte_carlo`.
*   **`compare_policies` (`/api/sim/compare`):** Takes two policies, runs a Monte Carlo simulation for both, and returns the side-by-side data to the frontend so the user can easily compare the outcomes of Policy A vs. Policy B.

### `backend/orchestrator/` (Future)
*   In the future, an **LLM+RAG** system will sit here. Instead of relying on the hardcoded dictionaries in `backend/simulation/policies.py`, the orchestrator will read a user's natural language prompt (e.g., "Implement a strict return-to-office mandate"), query the vector database for historical HR literature on RTO mandates, and dynamically generate the mathematical multipliers (`workload_multiplier`, `stress_gain_rate`) on the fly.
