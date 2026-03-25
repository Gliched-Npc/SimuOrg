# SimuOrg Engineering Roadmap
> **Last updated:** 2026-03-23  
> **Purpose:** Ordered, actionable checklist of every outstanding engineering item based on current codebase audit.

---

## Legend
- `[ ]` — Not started
- `[/]` — In progress / partial
- `[x]` — Complete

---

## Phase 1 — Stabilize Simulation System

### 1.1 Remove Global Mutable State

**Why it matters:** Module-level globals make concurrent requests clobber each other and make the system non-deterministic across users.

**Files to fix:**

| File | Global(s) to remove / isolate |
|---|---|
| `backend/core/ml/attrition_model.py` | `FEATURES`, `LABEL_ENCODERS` — currently mutated on each `train_attrition_model()` call |
| `backend/core/simulation/agent.py` | `_quit_model_cache`, `_quit_threshold` — lazily-loaded module globals |
| `backend/core/simulation/time_engine.py` | `_engine_calibration_cache` — module-level cache |
| `backend/api/upload_routes.py` | `_JOBS`, `_JOBS_LOCK`, `_last_data_issues` — in-memory shared state |

**Actions:**
- [ ] Wrap `FEATURES` and `LABEL_ENCODERS` in a `ModelArtifact` dataclass returned from `train_attrition_model()` instead of mutating globals.
- [ ] Replace `_quit_model_cache` in `agent.py` with a dependency-injection pattern — pass the loaded model into `EmployeeAgent` at construction time.
- [ ] Replace `_engine_calibration_cache` with a `CalibrationConfig` object passed into `run_simulation()` explicitly.
- [ ] Move `_last_data_issues` into the persistent DB (see Phase 3).

---

### 1.2 Enforce Deterministic Execution & Validate Reproducibility

**Why it matters:** Same seed must produce identical output across runs and across server restarts.

**Current state:** `run_simulation()` accepts a `seed` and uses `np.random.default_rng(seed)` ✅. But `load_agents_from_db()` uses `session.exec(select(Employee))` with no `ORDER BY` — DB row order is non-deterministic.

**Actions:**
- [ ] Add `ORDER BY employee_id` to all `session.exec(select(Employee))` calls in `time_engine.py` and `monte_carlo.py`.
- [ ] Add `ORDER BY` to any agent list comprehensions used as input to simulations.
- [ ] Write a reproducibility test: run the same `(config, seed)` twice and `assert results_a == results_b`.
- [ ] Add a `seed` parameter to `POST /api/sim/run` and `/api/sim/compare` so callers can pin results.

---

## Phase 2 — Async Execution with Celery + RabbitMQ

**Why it matters:** Training, calibration, and simulation are long-running (~60–120 s). The current `threading.Thread` approach is fragile, has no retry logic, no observability, and doesn't scale across processes.

### 2.1 Set Up Celery Application

- [ ] Install dependencies: `celery`, `redis` (or `amqp` for RabbitMQ), `flower` (monitoring UI).
- [ ] Fill in `backend/workers/celery_app.py`:
  ```python
  from celery import Celery
  import os

  celery_app = Celery(
      "simuorg",
      broker=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"),
      backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
  )
  celery_app.conf.task_serializer = "json"
  celery_app.conf.result_serializer = "json"
  ```
- [ ] Add `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` to `.env`.
- [ ] Add RabbitMQ + Redis services to `docker-compose.yml`.

### 2.2 Define Celery Tasks

Fill in `backend/workers/tasks.py`:

- [ ] `train_and_calibrate_task(job_id: str)` — wraps `train_attrition_model()` + `calibrate()`, writes status to DB.
- [ ] `run_simulation_task(job_id: str, policy_name: str, runs: int, duration_months: int, seed: int)` — wraps `run_monte_carlo()`, persists result to DB.
- [ ] Both tasks must update a `Job` DB record at each stage (see Phase 3).

### 2.3 Replace Threading in upload_routes.py

- [ ] Remove `threading.Thread(target=_background_train_and_calibrate, ...)`.
- [ ] Replace with `train_and_calibrate_task.delay(job_id)`.
- [ ] Remove `_JOBS` dict and `_JOBS_LOCK` — job state moves to DB.

### 2.4 Replace asyncio.to_thread in sim_routes.py

- [ ] `POST /api/sim/run` → dispatch `run_simulation_task.delay(...)`, return `{"job_id": ..., "poll_url": ...}` immediately.
- [ ] `POST /api/sim/compare` → dispatch two tasks, return two job IDs.
- [ ] Add `GET /api/sim/status/{job_id}` polling endpoint.

---

## Phase 3 — Persistent Storage for Jobs and Results

**Why it matters:** Jobs vanish on server restart. Simulation results can't be retrieved after the response closes.

### 3.1 Add DB Models

In `backend/db/models.py`, add:

- [ ] **`Job` table:**
  ```
  job_id (PK, str UUID)
  job_type (str: "training" | "simulation")
  status (str: "queued" | "running" | "completed" | "failed")
  created_at (datetime)
  updated_at (datetime)
  error (Optional[str])
  ```
- [ ] **`SimulationResult` table:**
  ```
  result_id (PK, str UUID)
  job_id (FK → Job)
  policy_name (str)
  runs (int)
  duration_months (int)
  seed (int)
  result_json (str/JSON)  ← aggregated MC output
  executive_summary_json (str/JSON)
  created_at (datetime)
  ```
- [ ] **`TrainingResult` table** (optional, or fold into `Job.result_json`):
  ```
  job_id (FK → Job)
  auc_roc (float)
  cv_auc_mean (float)
  signal_strength (str)
  calibration_json (str/JSON)
  ```
- [ ] Run `init_db()` (or an Alembic migration) to create new tables.

### 3.2 Update Job Status Flow

- [ ] Celery tasks write `Job.status` at every transition: `queued → running → completed / failed`.
- [ ] `GET /api/upload/status/{job_id}` reads from DB, not `_JOBS` dict.
- [ ] `GET /api/sim/status/{job_id}` reads from DB, includes result URL when complete.

---

## Phase 4 — Service Layer

**Why it matters:** API routes currently contain orchestration logic. This makes testing hard and mixes HTTP concerns with business logic.

### 4.1 Fill in Service Stubs

- [ ] **`backend/services/simulation_service.py`** — orchestration logic extracted from `sim_routes.py`:
  - `dispatch_simulation(policy_name, runs, duration_months, seed) → job_id`
  - `get_simulation_result(job_id) → SimulationResult | None`
  - `dispatch_comparison(policy_a, policy_b, runs, duration_months) → (job_id_a, job_id_b)`

- [ ] **`backend/services/report_service.py`** — result narration/export:
  - `get_executive_summary(job_id) → dict`
  - `export_result_as_csv(job_id) → bytes`

- [ ] **`backend/services/cleaning_report.py`** — data quality logic:
  - `get_last_data_issues(session) → list[dict]` (reads from DB, not module global)

### 4.2 Refactor Routes to Use Services

- [ ] `sim_routes.py` → call `simulation_service.*`, not `run_monte_carlo` directly.
- [ ] `upload_routes.py` → call `cleaning_report.get_last_data_issues()`, not `_last_data_issues` global.

---

## Phase 5 — Multi-User Safety

**Why it matters:** Two concurrent upload requests currently race on `FEATURES`, `LABEL_ENCODERS`, `_last_data_issues`, and agent caches.

**Actions:**
- [ ] Complete Phase 1.1 (remove globals) — this is the root fix.
- [ ] Each training job must operate on a private copy of model artifacts until it completes, then atomically swap the saved `.pkl` file.
- [ ] Use `Employee.simulation_id` field (already in schema) to scope simulation agent loads: `select(Employee).where(Employee.simulation_id == "master")` so future per-user simulations don't overlap.
- [ ] Consider per-request `simulation_id` generation for sandbox/what-if scenarios.

---

## Phase 6 — Object Storage (Planned)

**Why it matters:** ML model artifacts (`.pkl`), calibration JSON, and simulation results are written to the local filesystem. This breaks in containerized/distributed deployments.

**Actions:**
- [ ] Implement `backend/storage/storage.py` with an abstract `StorageBackend` interface:
  - `upload(key: str, data: bytes) → str` (returns URI)
  - `download(key: str) → bytes`
  - `exists(key: str) → bool`
- [ ] Implement `LocalFileBackend` first (wraps current file I/O).
- [ ] Implement `S3Backend` (boto3) as the production backend.
- [ ] Replace all `open(...)` / `joblib.dump(...)` in `attrition_model.py`, `calibration.py` with `storage.upload(...)`.
- [ ] Store uploaded CSV files in object storage keyed by `job_id`.

---

## Phase 7 — LLM / Natural Language (Planned)

- [ ] Implement `backend/api/llm_routes.py` with:
  - `POST /api/llm/summarize` — takes a `job_id`, returns a natural language summary of simulation results.
  - `POST /api/llm/chat` — conversational interface over simulation data.
- [ ] Implement `backend/core/llm/` module:
  - `llm_client.py` — wraps OpenAI / Gemini API.
  - `prompt_builder.py` — formats simulation result JSON as structured prompts.
- [ ] Add `OPENAI_API_KEY` (or equivalent) to `.env`.

---

## Phase 8 — RAG Integration (Planned)

- [ ] Choose a vector store (Chroma, Weaviate, or pgvector).
- [ ] Build an ingestion pipeline: after each simulation, embed the executive summary + monthly logs into the vector store.
- [ ] Implement `POST /api/llm/explain` — RAG-augmented endpoint that retrieves similar past simulations and uses them as context for explanation.

---

## Suggested Execution Order

```
Phase 1.2 (seeding/ordering) → Phase 1.1 (remove globals)
    → Phase 3.1 (DB models)
        → Phase 2.1/2.2 (Celery setup + tasks)
            → Phase 2.3/2.4 (replace threading in routes)
                → Phase 3.2 (job status via DB)
                    → Phase 4 (service layer)
                        → Phase 5 (multi-user safety audit)
                            → Phase 6 (object storage)
                                → Phase 7 → Phase 8
```

Phases 1–5 are blocking prerequisites for production stability.  
Phases 6–8 are independent and can be parallelized once Phase 5 is complete.
