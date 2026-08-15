import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';
const TOKEN_KEY = 'mediscan.token';

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      tokenStore.clear();
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export function errorMessage(error, fallback = 'Something went wrong.') {
  return error?.response?.data?.message || error?.message || fallback;
}

/** Translates Firebase Auth error codes into friendly messages. */
export function firebaseErrorMessage(error, fallback = 'Something went wrong.') {
  const message = error?.message || '';
  const code = error?.code || '';
  if (message.includes('Firebase is not configured')) {
    return 'Firebase is not configured. Add your keys to frontend/.env and restart the app.';
  }
  switch (code) {
    case 'auth/invalid-email':
      return 'Enter a valid email address.';
    case 'auth/user-not-found':
    case 'auth/wrong-password':
    case 'auth/invalid-credential':
      return 'Invalid email or password.';
    case 'auth/email-already-in-use':
      return 'An account with that email already exists.';
    case 'auth/weak-password':
      return 'Password must be at least 6 characters.';
    case 'auth/too-many-requests':
      return 'Too many attempts. Try again later.';
    case 'auth/network-request-failed':
      return 'Network error. Check your connection.';
    default:
      return error?.message || fallback;
  }
}

export const authApi = {
  register: (payload) => api.post('/auth/register', payload).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
};

export const scanApi = {
  diseases: () => api.get('/diseases').then((r) => r.data.diseases || []),
  health: () => api.get('/health').then((r) => r.data),
  analyze: (formData, onProgress) =>
    api
      .post('/scans/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: onProgress,
      })
      .then((r) => r.data),
  history: () => api.get('/scans').then((r) => r.data),
  remove: (id) => api.delete(`/scans/${id}`),
  heatmapUrl: (id) => `${BASE_URL}/scans/${id}/heatmap`,
  downloadReport: async (id) => {
    const response = await api.get(`/scans/${id}/report`, { responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `MediScan_Report_${id}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
  /** Authenticated image fetch: <img src> cannot send the bearer token. */
  fetchHeatmapBlob: async (id) => {
    const response = await api.get(`/scans/${id}/heatmap`, { responseType: 'blob' });
    return URL.createObjectURL(response.data);
  },
};

export const bridgeApi = {
  types: () => api.get('/medibridge/types').then((r) => r.data),
  nearby: ({ lat, lng, radiusKm, type }) =>
    api
      .get('/medibridge/resources/nearby', { params: { lat, lng, radiusKm, type } })
      .then((r) => r.data),
  all: (type) => api.get('/medibridge/resources', { params: { type } }).then((r) => r.data),
  updateStatus: (id, payload) =>
    api.post(`/medibridge/admin/resources/${id}/status`, payload).then((r) => r.data),
};

export const assistantApi = {
  status: () => api.get('/assistant/status').then((r) => r.data),
  chat: (message, history) =>
    api.post('/assistant/chat', { message, history }).then((r) => r.data),
};

/** Base origin (without /api) - needed for the SockJS handshake URL. */
export const SERVER_ORIGIN = BASE_URL.startsWith('http')
  ? BASE_URL.replace(/\/api\/?$/, '')
  : window.location.origin;


export default api;
