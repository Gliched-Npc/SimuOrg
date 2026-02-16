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

export default API;
