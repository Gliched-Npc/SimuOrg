# SimuOrg Backend Workflow & Architecture

This document provides a detailed, step-by-step breakdown of how the SimuOrg backend operates. The backend is built using **FastAPI**, with **SQLModel (SQLite)** for the database, and **Pandas/Scikit-Learn** for machine learning and data processing. 

The core functionality is split into two primary workflows:
1. **Data Ingestion & ML Training** (Setting up the environment)
2. **Simulation Engine & Monte Carlo Execution** (Running scenarios)

---

## 1. Data Ingestion & ML Training Workflow

When a user uploads a new dataset, the backend processes the data, stores it, and trains the underlying machine learning models used by the simulation.

**Endpoint:** `POST /api/upload/dataset`  
**File:** `backend/api/upload_routes.py`

### Step-by-Step Execution:
1. **File Validation:** Checks if a valid CSV file was uploaded.
2. **Parsing:** Reads the CSV into a pandas `DataFrame`.
3. **Normalization (`backend/schema.py`):** 
   - Standardizes column names (e.g., removing spaces).
   - Converts boolean-like columns (like `Attrition`, `OverTime`) into standardized 1/0 or Yes/No representations.
   - Applies default values for optional columns if they are missing.
4. **Data Quality & Validation (`backend/upload.py`):**
   - Validates that all `REQUIRED_COLUMNS` are present.
   - Cleans the dataframe by removing exact duplicate rows.
   - Generates a "Schema Report" to warn the user about data quality issues or missing optional fields.
5. **Database Ingestion:**
   - Initializes the SQLite database.
   - Inserts the cleaned rows into the `Employee` table (using SQLModel).
6. **Machine Learning Pipeline (`backend/ml/`):**
   - **Attrition Model (`train_attrition_model`):** Trains a Gradient Boosting classifier to predict the probability of an employee quitting based on their features (Age, JobRole, DistanceFromHome, etc.).
   - **Burnout Estimator (`train_burnout_estimator`):** Trains a separate regressor/estimator to baseline stress limits.
   - **Calibration (`calibrate`):** Calibrates the ML model outputs against the natural historical attrition rate found in the dataset, ensuring the simulation behaves realistically.

---

## 2. Simulation Workflow

When an HR manager or user initiates a simulation scenario (e.g., "What if we increase KPI pressure?"), the backend runs a Monte Carlo simulation forecasting month-by-month changes.

**Endpoints:** `POST /api/sim/run` and `POST /api/sim/compare`  
**Files:** `backend/api/sim_routes.py`, `backend/simulation/monte_carlo.py`

### Step-by-Step Execution:
1. **Request Validation:** Ensures that the requested policy (e.g., `baseline`, `kpi_pressure`) is defined in `POLICIES` (`backend/simulation/policies.py`).
2. **Database & Model Check:** Verifies that employee data exists in the database and that the ML model (`quit_probability.pkl`) has been trained.
3. **Policy Configuration:** Loads specific modifiers for the requested policy (e.g., `workload_multiplier`, `stress_gain_rate`, `duration_months`).
4. **Monte Carlo Orchestration (`monte_carlo.py`):**
   - Loads the base employee agents from the database *once*.
   - Deep-copies the initial state for $N$ runs (default is usually 10-50 runs).
   - Runs the **Time Engine** for each independent universe/run.
   - Aggregates the results across all runs to provide statistical bounds (Mean, Min, Max, Standard Deviation) for metrics like Headcount, Stress, and Productivity.

---

## 3. The Time Engine (The Core Simulation Loop)

For every single run within the Monte Carlo simulation, the Time Engine simulates the organization month-by-month.

**File:** `backend/simulation/time_engine.py`

### Preparing the Initial State
- **Agent Initialization:** Wraps each database `Employee` into an `EmployeeAgent` object (`backend/simulation/agent.py`), giving them dynamic psychological states (stress, motivation, fatigue).
- **Organization Graph (`org_graph.py`):** Builds a NetworkX directed graph linking employees to their managers and peers. This allows for "social contagion" computations.

### The Monthly Loop (Step-by-Step)
For every month from $1$ to $Duration_Months$, the engine performs the following phases:

#### 🟢 Phase 1: State Update (`behavior_engine.py`)
For every active agent, `update_agent_state()` is called:
- Calculates **Neighbor Influence:** Agents absorb a fraction of the stress from their peers and manager.
- Updates **Stress & Fatigue:** Modified by the policy's `workload_multiplier` and `stress_gain_rate`.
- Updates **Motivation & Satisfaction:** Motivation decays if stress is high. Overtime bonuses can temporarily prop up Job Satisfaction.
- Updates **Productivity:** Drops if an agent is chronically stressed or fatigues (burnout mechanics).

#### 🔴 Phase 2: Layoffs
If the current policy dictates a `layoff_ratio` > 0 (e.g., 5% workforce reduction):
- The engine identifies the lowest-performing active agents and marks them for removal.

#### 🟠 Phase 3: Voluntary Attrition (The ML Drop)
For the remaining active agents, the engine predicts their likelihood of quitting:
- Extracts the agent's current simulated features (features dynamically shift, e.g., JobSatisfaction drops over the months).
- Passes the features through the Scikit-Learn **Attrition Model**, fetching the *yearly probability* of quitting.
- Converts the yearly probability to a *monthly probability*.
- Rolls a random number; if the number is below the probability (scaled by calibration parameters), the agent is marked as voluntarily quitting.

#### 💥 Phase 4: Shockwave & Departures
For every agent that leaves (Layoff or Voluntary):
- **Attritional Shockwave:** `apply_attrition_shockwave()` is triggered on the Organization Graph. The departed agent's immediate neighbors suffer an immediate spike in **Stress** and a drop in **Loyalty**.
- The agent is removed from the active roster and the Organization Graph.

#### 🔵 Phase 5: Hiring / Replacements
If `hiring_active` is true in the policy:
- The engine spawns a new `EmployeeAgent` for every voluntary quit.
- The new hire inherits the departed employee's role, department, and manager, but starts with fresh stats (0 years at company, baseline stress, random lower age).
- The new hire is wired into the Organization Graph under the same manager.

#### 🟡 Phase 6: Monthly Metrics Collection
The engine calculates the organizational averages for the month:
- Active Headcount, Number of Quits/Layoffs.
- Average Stress, Productivity, Motivation, Job Satisfaction, Work-Life Balance.
- Total count of employees crossing the "Burnout Boundary".
- These metrics are saved into the `logs` array.

---

## 4. Summary & Output Response
After the `duration_months` loop finishes for all runs, the Monte Carlo aggregator zips the data and sends a JSON payload back to the frontend. 

The frontend uses this statistical time-series data to draw the predictive charts and gauge the overall impact of the chosen organizational policy.
