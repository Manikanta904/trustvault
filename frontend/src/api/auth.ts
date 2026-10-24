import { apiClient } from './client';
import type { TokenResponse, User } from '../types';

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
}

export async function loginApi(email: string, password: string): Promise<TokenResponse> {
  const params = new URLSearchParams();
  params.append('username', email.trim().toLowerCase());
  params.append('password', password);

  const response = await apiClient.post<TokenResponse>('/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
}

export async function registerApi(payload: RegisterPayload): Promise<User> {
  const response = await apiClient.post<User>('/auth/register', {
    name: payload.name.trim(),
    email: payload.email.trim().toLowerCase(),
    password: payload.password,
  });
  return response.data;
}

export async function getMeApi(): Promise<User> {
  const response = await apiClient.get<User>('/auth/me');
  return response.data;
}

export async function checkHealthApi(): Promise<{ status: string }> {
  const response = await apiClient.get<{ status: string }>('/health');
  return response.data;
}
