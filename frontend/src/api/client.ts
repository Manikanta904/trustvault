import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('trustvault_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear token on 401 Unauthorized
      localStorage.removeItem('trustvault_token');
      // If not already on login or register, notify or redirect
      if (
        typeof window !== 'undefined' &&
        !window.location.pathname.startsWith('/login') &&
        !window.location.pathname.startsWith('/register')
      ) {
        window.dispatchEvent(new Event('auth:unauthorized'));
      }
    }
    return Promise.reject(error);
  }
);

interface FastApiValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export function extractErrorMessage(error: unknown, fallbackMessage = 'An unexpected error occurred'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data) {
      if (typeof data.detail === 'string') {
        return data.detail;
      }
      if (Array.isArray(data.detail)) {
        // FastAPI 422 validation error array
        return data.detail
          .map((err: FastApiValidationError) => {
            const field = err.loc ? err.loc.slice(1).join('.') : '';
            return field ? `${field}: ${err.msg}` : err.msg;
          })
          .join(', ');
      }
      if (typeof data.message === 'string') {
        return data.message;
      }
    }
    if (error.message === 'Network Error') {
      return 'Unable to connect to the backend server. Please verify the API is running.';
    }
    return error.message || fallbackMessage;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallbackMessage;
}
