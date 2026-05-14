import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:3001/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

export default api;

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login:    (data) => api.post('/auth/login', data),
};

// ── Users ─────────────────────────────────────────────────────────────────────
export const usersApi = {
  me:               ()     => api.get('/users/me'),
  updateOnboarding: (data) => api.put('/users/me/onboarding', data),
  updateProfile:    (data) => api.put('/users/me/profile', data),
};

// ── Tracks ────────────────────────────────────────────────────────────────────
export const tracksApi = {
  search:        (q, limit = 20) => api.get('/tracks/search', { params: { q, limit } }),
  getById:       (id)            => api.get(`/tracks/${id}`),
  itunesPreview: (id)            => api.get(`/tracks/${id}/itunes-preview`),
};

// ── Play ──────────────────────────────────────────────────────────────────────
export const playApi = {
  record: (trackId) => api.post(`/play/${trackId}`),
};

// ── Recommendations ───────────────────────────────────────────────────────────
export const recApi = {
  hybrid:  ()        => api.get('/recommendations'),
  similar: (trackId) => api.get(`/recommendations/similar/${trackId}`),
};

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  stats:           ()                      => api.get('/admin/stats'),
  triggerTraining: ()                      => api.post('/admin/trigger-training'),
  evaluate:        ()                      => api.get('/admin/evaluate'),
  evaluateCb:      ()                      => api.get('/admin/evaluate/cb'),
  listUsers:       (page = 1, limit = 20)  => api.get('/admin/users', { params: { page, limit } }),
  deleteUser:      (id)                    => api.delete(`/admin/users/${id}`),
};
