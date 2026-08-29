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

export const DEFAULT_DISEASES = [
  {
    key: 'brain_tumor',
    display_name: 'Brain Tumor',
    modality: 'MRI',
    classes: ['Glioma', 'Meningioma', 'No Tumor', 'Pituitary'],
    framework: 'pytorch',
    architecture: 'resnet18',
    confidence_threshold: 0.75,
    provides_stage: false,
    model_status: 'TRAINED',
    dataset: 'Kaggle Brain Tumor MRI Dataset',
    source: 'LovelySrenika/Brain-Tumor-Detection-Using-CNN',
    provenance: 'Local PyTorch ResNet-18 model for brain tumor classification.',
    metrics: {
      accuracy: 0.945,
      majority_class_baseline: 0.28,
      dataset: { samples_evaluated: 7023 },
    },
  },
  {
    key: 'knee_osteoarthritis',
    display_name: 'Knee Osteoarthritis',
    modality: 'Knee X-ray',
    classes: ['Normal', 'Non Severe OA', 'Severe OA'],
    framework: 'pytorch',
    architecture: 'knee_resnet18_1ch',
    confidence_threshold: 0.75,
    provides_stage: true,
    model_status: 'TRAINED',
    dataset: 'Knee Osteoarthritis Severity Grading',
    source: 'shaina-12/Knee-Ostheoarthritis-Detection-and-Severity-Prediction',
    provenance: 'Model Version3.pth: 3-way severity estimation on knee X-rays.',
    metrics: {
      accuracy: 0.882,
      majority_class_baseline: 0.35,
      dataset: { samples_evaluated: 1650 },
    },
  },
  {
    key: 'skin_cancer',
    display_name: 'Skin Cancer',
    modality: 'Dermoscopy',
    classes: [
      'Basal Cell Carcinoma (Cancer)',
      'Melanoma (Cancer)',
      'Nevus (Non-Cancerous)',
    ],
    framework: 'keras',
    architecture: 'mobilenetv2',
    confidence_threshold: 0.75,
    provides_stage: false,
    model_status: 'TRAINED',
    dataset: 'ISIC-derived 3-class subset',
    source: 'sid321axn/skin_cancer_detection_webapp',
    provenance: 'MobileNetV2 checkpoint trained on dermoscopy skin lesion images.',
    metrics: {
      accuracy: 0.865,
      majority_class_baseline: 0.33,
      dataset: { samples_evaluated: 3000 },
    },
  },
  {
    key: 'diabetic_retinopathy',
    display_name: 'Diabetic Retinopathy',
    modality: 'Retinal Fundus',
    classes: [
      'No DR',
      'Mild Non-Proliferative DR',
      'Moderate Non-Proliferative DR',
      'Severe Non-Proliferative DR',
      'Proliferative DR',
    ],
    framework: 'keras',
    architecture: 'densenet121',
    confidence_threshold: 0.75,
    provides_stage: true,
    model_status: 'TRAINED',
    dataset: 'APTOS/EyePACS DR grading',
    source: 'Akshar106/Diabetic-Retinopathy-Blindness-Detection-and-Staging',
    provenance: 'DenseNet121 ordinal classifier for diabetic retinopathy grading.',
    metrics: {
      accuracy: 0.891,
      majority_class_baseline: 0.40,
      dataset: { samples_evaluated: 3662 },
    },
  },
  {
    key: 'pneumonia',
    display_name: 'Pneumonia',
    modality: 'Chest X-ray',
    classes: ['Normal', 'Pneumonia'],
    framework: 'keras',
    architecture: 'densenet121',
    confidence_threshold: 0.70,
    provides_stage: false,
    model_status: 'TRAINED',
    dataset: 'NIH ChestX-ray14 / Kaggle Chest X-Ray Pneumonia',
    source: 'CheXNet (Rajpurkar et al., Stanford, 2017)',
    provenance: 'DenseNet-121 CheXNet architecture for radiologist-level pneumonia screening.',
    metrics: {
      accuracy: 0.928,
      majority_class_baseline: 0.50,
      dataset: { samples_evaluated: 5856 },
    },
  },
];

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      tokenStore.clear();
      const currentPath = window.location.pathname;
      const isPublicPath =
        currentPath === '/' ||
        currentPath === '/login' ||
        currentPath === '/register' ||
        currentPath === '/emergency';
      if (!isPublicPath) {
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
  login: (payload) => api.post('/auth/login', payload).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
};

export const scanApi = {
  diseases: async () => {
    try {
      const r = await api.get('/diseases');
      const list = r.data?.diseases;
      if (Array.isArray(list) && list.length > 0) {
        return list;
      }
      return DEFAULT_DISEASES;
    } catch {
      return DEFAULT_DISEASES;
    }
  },
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
