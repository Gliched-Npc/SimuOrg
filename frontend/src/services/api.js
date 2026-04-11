import axios from 'axios';

const API = axios.create({
    baseURL: 'http://localhost:8000/api',
});

// Attach JWT token to every request if it exists
API.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// --- Simulation ---
export const fetchTestData = () => API.get('/sim/test-data');

// --- Auth ---
export const loginUser = (credentials) => API.post('/auth/login', credentials);
export const registerUser = (userData) => API.post('/auth/register', userData);

// --- Orchestration (Async) ---

/**
 * Submit an orchestration request. Returns {job_id, status: 'queued'} immediately.
 * The heavy work (sim + LLM) runs in the Celery worker.
 */
export const submitOrchestrate = (userText) =>
    API.post('/llm/orchestrate', { user_text: userText });

/**
 * Poll orchestration job status.
 * Returns {job_id, status, result?, error?}
 * status: 'queued' | 'running' | 'completed' | 'failed'
 */
export const getOrchestrateStatus = (jobId) =>
    API.get(`/llm/orchestrate/status/${jobId}`);

/**
 * Helper: submit and poll until done.
 * @param {string} userText  - CEO policy input
 * @param {function} onStatus - called on each poll with the current status string
 * @param {number} intervalMs - polling interval (default 2500ms)
 * @returns {Promise<object>} - final result payload
 */
export const orchestrateAndPoll = async (userText, onStatus = () => {}, intervalMs = 2500) => {
    const { data: { job_id } } = await submitOrchestrate(userText);

    return new Promise((resolve, reject) => {
        const poll = setInterval(async () => {
            try {
                const { data } = await getOrchestrateStatus(job_id);
                onStatus(data.status);

                if (data.status === 'completed') {
                    clearInterval(poll);
                    resolve(data.result);
                } else if (data.status === 'failed') {
                    clearInterval(poll);
                    reject(new Error(data.error || 'Orchestration failed'));
                }
            } catch (err) {
                clearInterval(poll);
                reject(err);
            }
        }, intervalMs);
    });
};

export default API;
