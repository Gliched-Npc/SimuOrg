# SimuOrg Backend — Status & Technical Notes

> Last updated: 2026-02-23

---

## 1. Dataset

### Source
- **Original**: IBM HR Attrition dataset from Kaggle (4,410 rows × 29 columns)
- **Master**: `backend/data/SimuOrg_Master_Dataset.csv` (4,410 rows × 30 columns)
- **Only difference**: `ManagerID` column — algorithmically derived from `JobLevel` to create org hierarchy

### Why Not AI-Generated Data?
AI-generated datasets produce ~64% test accuracy vs ~86% with the real Kaggle data because:
- Features are generated independently (no inter-feature correlations)
- No realistic causal patterns (e.g., low income + low level → higher attrition)
- Missing conditional dependencies that real HR data naturally has

The Kaggle dataset is a valid PoC representation of real HRIS data. In production, companies would export similar data from Workday/SAP/BambooHR.

---

## 2. ML Model — Top Attrition Predictors

The XGBoost classifier uses **21 features** (16 raw + 5 engineered):

### Raw Features
| Feature | Category | Why It Matters |
|---------|----------|----------------|
| `monthly_income` | Financial | Underpaid employees leave |
| `job_satisfaction` | Satisfaction | Unhappy = exit |
| `work_life_balance` | Satisfaction | Poor balance → burnout |
| `environment_satisfaction` | Satisfaction | Toxic environment drives exits |
| `job_involvement` | Engagement | Low involvement = disengaged |
| `years_at_company` | Tenure | Short tenure = flight risk |
| `total_working_years` | Experience | Early-career employees leave more |
| `num_companies_worked` | History | Job-hoppers have higher risk |
| `job_level` | Career | Lower levels quit more |
| `years_since_last_promotion` | Growth | Stagnation drives attrition |
| `years_with_curr_manager` | Relationship | Manager quality matters |
| `performance_rating` | Performance | High performers may leave if underpaid |
| `stock_option_level` | Financial | Options = golden handcuffs |
| `age` | Demographics | Younger = more mobile |
| `distance_from_home` | Logistics | Long commute = higher quit risk |
| `percent_salary_hike` | Financial | Low raises → dissatisfaction |

### Engineered Features
| Feature | Formula | Signal |
|---------|---------|--------|
| `stagnation_score` | `years_since_last_promotion / (years_at_company + 1)` | Stuck with no growth |
| `satisfaction_composite` | `(job_sat + wlb + env_sat) / 3` | Overall happiness |
| `career_velocity` | `job_level / (total_working_years + 1)` | Growth speed |
| `loyalty_index` | `years_at_company / (total_working_years + 1)` | Company commitment |
| `is_single` | `marital_status == 'Single'` → 1/0 | Fewer geographic anchors |

### Model Performance
- **Test Accuracy**: ~86%
- **AUC-ROC**: 0.86
- **Cross-Validation Mean AUC**: 0.92 ± 0.01
- **Signal Strength**: Strong

---

## 3. Backend Health Check

### Module Status

| Module | Status | Notes |
|--------|:------:|-------|
| Database (`database.py`, `models.py`) | ✅ | PostgreSQL with SQLModel |
| Upload & Cleaning (`upload.py`) | ✅ | Robust null handling, validation |
| Attrition Model (`attrition_model.py`) | ✅ | XGBoost + SMOTE + threshold tuning |
| Burnout Estimator (`burnout_estimator.py`) | ✅ | Rule-based, deterministic |
| Calibration (`calibration.py`) | ✅ | Data-driven config generation |
| Agent (`agent.py`) | ✅ | Feature pipeline matches ML model |
| Behavior Engine (`behavior_engine.py`) | ✅ | Stress/fatigue/motivation dynamics |
| Org Graph (`org_graph.py`) | ✅ | 3-layer graph with dynamic weights |
| Time Engine (`time_engine.py`) | ✅ | Full simulation loop with summary |
| Monte Carlo (`monte_carlo.py`) | ✅ | Multi-run aggregation |
| Policies (`policies.py`) | ✅ | 6 policies with tuned values |
| API Routes (`sim_routes.py`, `upload_routes.py`) | ✅ | `/api/sim/run`, `/api/sim/compare`, `/api/upload/dataset` |
| Explainable AI (`explain.py`) | ✅ | SHAP values for employee attrition |
| ML API Routes (`ml_routes.py`) | ✅ | `/api/ml/explain/{employee_id}` |
| Orchestrator (LLM) | 🔲 | Placeholder — pending |
| Auth | 🔲 | Placeholder — pending |

### Bugs Fixed During Review
1. **`stress_gain_rate` was dead code** — Policy parameter was accepted but never used in `behavior_engine.py`. Fixed by multiplying it into the stress calculation.
2. **Policy values tuned** — `kpi_pressure` was producing ~52% attrition (unrealistic). Retuned to ~25-30%.

---

## 4. Simulation — How Stress & Attrition Work

### The Stress Formula
```
stress_gain = STRESS_GAIN_RATE × workload_multiplier × stress_gain_rate
            + 0.01 × neighbor_stress
            + 0.005 × fatigue
            - 0.001 × communication_quality
```

- `STRESS_GAIN_RATE` = calibrated from real data (currently 0.0132)
- `workload_multiplier` = policy parameter
- `stress_gain_rate` = policy parameter (multiplier on top)

### Attrition Spiral (Why Quits Accelerate Late)
The simulation correctly models "turnover contagion":
1. **Stress accumulates** → more employees cross burnout threshold
2. **Quits trigger shockwaves** → neighbors get stressed
3. **Stress feeds fatigue** → fatigue amplifies stress (positive feedback loop)
4. **Motivation decays** → satisfaction drops → ML quit probability rises

This matches real-world HR patterns where attrition is slow initially, then accelerates as a cascade.

### Safety Caps
- Stress hard-capped at 1.0
- Recovery rate pulls stress back each month
- Hiring replaces voluntary quits (new hires start fresh)
- Employees must pass 3 conditions to quit (stress > threshold AND ML prob > threshold AND random check)

---

## 5. Policy Parameters

### Current Tuned Values
| Policy | Workload | Stress Rate | Motivation Decay | Shock | Hiring |
|--------|:---:|:---:|:---:|:---:|:---:|
| Baseline | 1.0 | 1.0 | 0.005 | 0.2 | ✅ |
| Remote Work | 0.9 | 0.8 | 0.004 | 0.15 | ✅ |
| KPI Pressure | 1.3 | 1.2 | 0.008 | 0.25 | ✅ |
| Hiring Freeze | 1.2 | 1.0 | 0.008 | 0.25 | ❌ |
| Layoff | 1.0 | 1.8 | 0.02 | 0.4 | ❌ |
| Promotion Freeze | 1.1 | 1.0 | 0.02 | 0.2 | ✅ |

### Why These Are Hardcoded (For Now)
These values are PoC placeholders. In production, the **LLM + RAG orchestrator** will replace them:

```
User: "Simulate what happens if we push aggressive quarterly KPIs"
  ↓
RAG retrieves HR research benchmarks
  ↓
LLM generates grounded SimulationConfig values
  ↓
Simulation runs → LLM validates output against industry benchmarks
  ↓
If unrealistic → auto-adjusts and reruns
```

The orchestrator (`backend/orchestrator/`) will translate natural language policy descriptions into data-driven simulation parameters, grounded in retrieved HR research.

---

## 6. Pending Work

| Component | Purpose | Priority |
|-----------|---------|----------|
| LLM + RAG Orchestrator | Natural language → policy parameters | High |
| Authentication | API auth middleware | Medium |
| Centralized Config | `config.py` for environment settings | Medium |
| Frontend (React/Vite) | Dashboard for simulation results | After backend complete |
