# SimuOrg: Backend All-in-One Master Manual

Welcome to the definitive guide for the SimuOrg Backend. This document consolidates all technical deep-dives into a single, cohesive narrative. It explains how Machine Learning, Agent-Based Simulation, and REST Orchestration work together to predict the future of work.

---

## 1. Executive Summary: The SimuOrg Workflow
SimuOrg is a hybrid intelligence platform. It uses **Statistical ML** to learn historical patterns and **Agent-Based Simulation** to project those patterns into active "what-if" scenarios.

1.  **Ingestion & Cleaning**: Raw HR data is sanitized and ingested.
2.  **ML Training**: An XGBoost model calculates baseline flight risk.
3.  **Behavioral Tuning**: The simulation engine "self-calibrates" to match the ML results.
4.  **Policy Simulation**: Users apply policies (e.g., Remote Work) and the engine models the behavioral ripple effects.
5.  **Executive Insight**: The system provides narratives and SHAP graphs to explain the *Why* behind the projections.

---

## 2. Part I: The Machine Learning Pipeline

### Feature Engineering
We don’t just use raw data. We create **Signal Boosters**:
*   **Stagnation Score**: Identifies employees trapped in their roles.
*   **Income vs. Level**: Detects relative compensation dissatisfaction.
*   **Loyalty Index**: Measures organizational commitment relative to total career.

### The Predictive Engine
*   **Model**: XGBoost with `scale_pos_weight` to handle the rarity of quitters.
*   **Calibration**: **Isotonic Regression** to map mathematical scores to real-world probabilities.
*   **Thresholding**: A dynamic search for the "CEO-Optimal" threshold to maximize recall (catching at-risk employees).

---

## 3. Part II: The Simulation Physics

### The Social Graph
The organization is modeled as a graph where nodes are agents and edges are relationships (Manager $\rightarrow$ Direct Report). Stress flows through these edges.

### Behavioral State Updates
Each month, agents update their internal state:
*   **Stress**: Increases with workload (quadratic) and peer pressure; decreases with pay and WLB.
*   **Fatigue**: Accumulates when stress is consistently high.
*   **Motivation**: Decays under toxic environments; recovers under sustainable workloads.
*   **Productivity**: Non-linearly affected by burnout.

### The Shockwave Effect
Departures are contagious. When an agent leaves, their neighbors feel a "Shockwave" of stress and a drop in loyalty.

---

## 4. Part III: The API & Orchestration

### Asynchronous Operations
Training and simulation are expensive. The API uses:
*   **Background Threads**: To keep the UI responsive during 60-second training jobs.
*   **Job Polling**: A registry system (`/api/upload/status`) tracks background progress.
*   **Parallel MC Runs**: Using `asyncio.gather` to double the speed of "Scenario Comparisons."

### Explainable AI (XAI)
The API isn't just a data pipe; it's an interpreter:
*   **SHAP Force Plots**: Providing the mathematical reason for every prediction.
*   **Business Intelligence**: A recommendation engine that identifies patterns like "Veteran Stagnation" or "Managerial Friction."

---

## 5. The Operational Example: A Step-by-Step Simulation

### Scenario: "The 1.5x KPI Push"
Administrator uploads 1,000 employee records and chooses the "KPI Pressure" policy (1.5x Workload).

#### Month 1: The Initial Roll
*   The engine calculates baseline `QuitProbs` for all 1,000 agents.
*   The `behavior_engine` applies the 1.5x workload.
*   Agent **#505** (a high-productivity analyst) sees their `stress` rise from 0.15 to 0.28.

#### Month 4: The Burnout Trigger
*   Agent **#505** has been under pressure for 4 months. Their `fatigue` is now 0.40.
*   Their [productivity](file:///c:/Data%20Science/Dummy%20folder/SimuOrg/backend/simulation/agent.py#162-170) drops from 100% to 88% as they hit their internal `burnout_limit`.

#### Month 6: The Resignation
*   Agent **#505**'s `QuitProb` was originally 2% per month. Due to high stress, the `StressAmp` (calibrated at 2.5x) kicks in.
*   `EffectiveProb = 0.02 * 2.5 = 0.05`.
*   The random dice roll hits. **Agent #505 quits.**

#### Month 6 (Instant): The Shockwave
*   Agent **#506** (a teammate of #505) instantly receives a +0.05 `stress` hit.
*   The "Social Graph" transmits the resignation shock.
*   Team morale drops; `loyalty` scores across the department are reduced.

#### Month 12: The Verdict
*   The simulation ends.
*   **Result**: 15% annual attrition (was 10% baseline).
*   **Narrative**: "The KPI Push resulted in a 5% attrition spike, primarily driven by star-performer burnout in the Sales department."

---

## 6. Full Logic Interaction Diagram

graph TD
    A[User Uploads CSV] --> B[Data Validation & Ingestion]
    B --> C[Background: ML Training]
    C --> D[Background: Simulation Calibration]
    D --> E[Calibration JSON Exported]
    E --> F[User Runs Scenario]
    F --> G[Monte Carlo Engine Starts]
    G --> H[Behavior Engine Loop]
    H --> I[Agent State Updates]
    I --> J[Probabilistic Departure Roll]
    J --> K[Aggregate Logs & Summary]
    K --> L[API Sends Result to Frontend]
