import { apiClient } from './client';
import type { UserSearchResult } from '../types';

export async function searchUsersApi(query: string, limit = 10): Promise<UserSearchResult[]> {
  const response = await apiClient.get<UserSearchResult[]>('/users/search', {
    params: { q: query, limit },
  });
  return response.data;
}
