import axios from "axios";

const API = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL
    ? `${import.meta.env.VITE_API_BASE_URL}/api`
    : "http://127.0.0.1:8000/api",
});

// Generate or retrieve session ID
function getSessionId() {
  let sessionId = localStorage.getItem("simuorg_session_id");
  if (!sessionId) {
    try {
      sessionId = crypto.randomUUID();
    } catch (e) {
      // Fallback for older browsers
      sessionId = "10000000-1000-4000-8000-100000000000".replace(
        /[018]/g,
        (c) =>
          (
            c ^
            (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))
          ).toString(16),
      );
    }
    localStorage.setItem("simuorg_session_id", sessionId);
  }
  return sessionId;
}

// Attach JWT token and Session ID to every request
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  config.headers["X-Session-ID"] = getSessionId();
  return config;
});

// ── Simulation ─────────────────────────────────────────────
export const fetchTestData = () => API.get("/sim/test-data");
export const getEmployees = () => API.get("/sim/test-data");

// ── Auth ────────────────────────────────────────────────────
export const loginUser = (credentials) => API.post("/auth/login", credentials);
export const registerUser = (userData) => API.post("/auth/register", userData);

// ── Upload ──────────────────────────────────────────────────
export const validateDataset = (file) => {
  const form = new FormData();
  form.append("file", file);
  return API.post("/upload/validate", form);
};

export const uploadDataset = (file) => {
  const form = new FormData();
  form.append("file", file);
  return API.post("/upload/dataset", form);
};

export const getTrainingStatus = (jobId) => API.get(`/upload/status/${jobId}`);
export const getDatasetMetadata = () => API.get("/upload/metadata");

// ── ML & XAI ────────────────────────────────────────────────
export const getFeatureImportance = () => API.get("/ml/feature-importance");
export const getModelMetrics = () => API.get("/ml/metrics");

// ── Orchestration (Async) ──────────────────────────────────

/**
 * Submit an orchestration request. Returns {job_id, status: 'queued'} immediately.
 * The heavy work (sim + LLM) runs in the Celery worker.
 */
export const submitOrchestrate = (userText) =>
  API.post("/llm/orchestrate", { user_text: userText });
export const getOrchestrateStatus = (jobId) =>
  API.get(`/llm/orchestrate/status/${jobId}`);

/**
 * Helper: submit and poll until done.
 * NOW returns { result, job_id } for session persistence.
 * @param {string}   userText    - CEO policy input
 * @param {function} onStatus    - called on each poll with the current status string
 * @param {number}   intervalMs  - polling interval (default 2500ms)
 * @returns {Promise<{result: object, job_id: string}>}
 */
export const orchestrateAndPoll = async (
  userText,
  onStatus = () => {},
  intervalMs = 2500,
) => {
  const {
    data: { job_id },
  } = await submitOrchestrate(userText);

  // Persist job_id immediately so session can be restored on reload
  localStorage.setItem("simuorg_last_job_id", job_id);

  return new Promise((resolve, reject) => {
    const poll = setInterval(async () => {
      try {
        const { data } = await getOrchestrateStatus(job_id);
        onStatus(data.status);

        if (data.status === "completed") {
          clearInterval(poll);
          resolve({ result: data.result, job_id }); // ← returns job_id now
        } else if (data.status === "failed") {
          clearInterval(poll);
          reject(new Error(data.error || "Orchestration failed"));
        }
      } catch (err) {
        clearInterval(poll);
        reject(err);
      }
    }, intervalMs);
  });
};

export default API;
