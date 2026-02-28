# Comprehensive Project Progress Report: SimuOrg Development

This document provides an exhaustive, end-to-end overview of everything accomplished in the SimuOrg project to date. This encompasses the foundational architecture, the data ingestion pipeline, the machine learning models, the simulation engine, recent bug fixes, and the newly integrated Explainable AI (XAI) features.

---

## Phase 1: Foundation & Architecture

### 1. Core Framework Setup
- **Web Framework:** Initialized a robust, asynchronous REST API backend using **FastAPI** (`backend/main.py`), complete with CORS middleware for frontend communication.
- **Database Architecture:** Implemented an **SQLite** database (`simuorg.db`) using **SQLModel** and **SQLAlchemy** (`backend/database.py`).
- **Data Models:** Designed the `Employee` ORM model (`backend/models.py`) to strictly map to our HR dataset capabilities, enforcing type safety across the application.
- **Project Restructuring:** Segmented the codebase into five distinct, modular pillars (Foundation, Data Ingestion, Machine Learning, Simulation, and API Orchestration) and generated comprehensive architectural documentation (`backend_working_documentation.md`).

---

## Phase 2: Data Ingestion & Preprocessing Pipeline

To ensure the Simulation and ML models receive high-quality data, we built a highly fault-tolerant data ingestion pipeline.

### 1. Robust Upload & Cleaning (`backend/upload.py`)
- Created an endpoint (`POST /api/upload/dataset`) that accepts raw CSV files.
- Implemented data validation to clean datasets by removing duplicate rows and ensuring strict schema adherence for required columns (e.g., `EmployeeID`).
- Added a logical validation layer that detects impossibilities (e.g., employees younger than 18 or negative salaries) and generating warnings.
- Built bulk-insert capabilities to efficiently ingest thousands of rows into the database at once.

### 2. Intelligent Data Normalization (`backend/schema.py`)
- Developed a fuzzy-matching translation layer that gracefully handles messy, real-world HR data (e.g., resolving column name variations like "Monthly Income" vs "Monthly_Income").
- Built auto-derivation mechanics to guess or calculate missing columns (e.g., deriving `YearsSinceLastPromotion` from `NumberOfPromotions`).
- Designed auto-encoders to translate text ratings (e.g., "Low", "High") and boolean flags ("Yes", "Left") into machine-readable numeric scales (1-4, 0/1).
- Implemented a "Schema Report" generator that provides a CEO-friendly JSON summary of data quality upon upload.

### 3. Debugging Data Quality
- **ML Accuracy Drop Resolution:** Recently identified and fixed a critical bug where the testing dataset (`test.csv`) was dropping the model's accuracy to random chance (~50%). 
- Resolved the issue by hardening the ingestion pipeline against missing columns and unexpected spaces, allowing the model to hit its expected ~86% accuracy ceiling.

---

## Phase 3: Machine Learning Pipeline

### 1. Attrition Prediction Model (`backend/ml/attrition_model.py`)
- Engineered 5 powerful synthetic features (e.g., `satisfaction_composite`, `stagnation_score`, `career_velocity`) on top of 16 raw features to boost signal strength.
- Trained an **XGBoost Classifier** supplemented with **SMOTE** (to handle class imbalances) to predict the binary probability of an employee quitting.
- Successfully achieved a test accuracy of ~86% (AUC 0.88) on the master dataset.
- Analyzed and documented the binarization logic for targeting arrays `labels = (df_all["attrition"] == "Yes").astype(int).values`.

### 2. Behavioral Calibration (`backend/ml/calibration.py`)
- Built an automated calibration script that evaluates the company's historical natural attrition rate and dynamically calculates behavioral baselines (like `stress_gain_rate` and `recovery_rate`).
- Grounded the simulation in reality by matching output stress metrics to average organizational Job Satisfaction and Work-Life Balance.


---

## Phase 4: Simulation Engine (The Core)

We built a highly complex, time-series Monte Carlo simulation engine that forecasts human behavior under varying HR policies.

### 1. Agent & Network Dynamics
- **Employee Agents:** Wrapped static database rows into dynamic `EmployeeAgent` instances (`backend/simulation/agent.py`) with mutable psychological states (Stress, Motivation, Fatigue).
- **Organization Graph:** Used **NetworkX** to build a dynamic, directed graph (`backend/simulation/org_graph.py`) layering employees by manager hierarchies, enabling us to model social influence and "Turnover Contagion".

### 2. Behavior Engine (`backend/simulation/behavior_engine.py`)
- Programmed a month-to-month psychological engine detailing exactly how agents respond to pressure.
- **Stress Cascades:** Modeled how stress bleeds from managers to direct reports, and how an employee quitting triggers an immediate shockwave of stress to their peers.
- **Productivity & Burnout:** Implemented a `burnout_estimator` that calculates unique stress thresholds for employees based on seniority and experience, dropping their productivity if they cross the line.

### 3. Policy Execution & The Time Engine
- **Policies:** Created a suite of pre-defined HR policies (`policies.py`) such as "KPI Pressure", "4-Day Work Week", and "Remote Work" that apply mathematical multipliers to the workforce.
- **Time Engine (`backend/simulation/time_engine.py`):** The orchestrator loop that loops through months, updating states, applying layoffs, running the ML model to calculate voluntary quits, executing shockwaves, and hiring replacement clones.
- **Monte Carlo Wrapper (`backend/simulation/monte_carlo.py`):** Runs the simulation simultaneously across dozens of parallel universes to return statistically valid averages, worst-case lines, and best-case lines to the frontend.

### 4. Recent Simulation Debugging
- **KPI Pressure Adjustments:** Discovered that extreme policies (like KPI Pressure) were not yielding realistically dramatic attrition (only shifting from 16% to 18%).
- **Behavioral Fixes:** Fixed dead-code where `stress_gain_rate` was not being appropriately utilized. Adjusted the bounding constraints and the behavioral link between the simulated stress state and the ML model's quit probability logic to ensure extreme policies exhibit realistic consequences.
- Tuned multiple policy configurations to yield grounded outcomes (e.g., retuning KPI pressure outputs to a realistic ~25-30% attrition rate).

---

## Next Steps: Roadmap
- **LLM + RAG Orchestrator:** Currently preparing for the impending implementation of a Retrieval-Augmented Generation agent (`backend/orchestrator/`), which will ingest natural language prompts (e.g., "What happens if we mandate 5 days in office?"), ground the prompt in HR research benchmarks, and dynamically generate the numeric configuration multipliers for the simulation.
