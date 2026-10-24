import { apiClient } from './client';
import type { AuditLogFilterParams, AuditLogsResponse } from '../types';

export async function listAuditLogsApi(params?: AuditLogFilterParams): Promise<AuditLogsResponse> {
  const queryParams: Record<string, string | number> = {};
  if (params?.action) queryParams.action = params.action;
  if (params?.outcome) queryParams.outcome = params.outcome;
  if (params?.actor_id) queryParams.actor_id = params.actor_id;
  if (params?.document_id) queryParams.document_id = params.document_id;
  if (params?.start_date) queryParams.start_date = params.start_date;
  if (params?.end_date) queryParams.end_date = params.end_date;
  if (params?.limit !== undefined) queryParams.limit = params.limit;
  if (params?.offset !== undefined) queryParams.offset = params.offset;

  const response = await apiClient.get<AuditLogsResponse>('/admin/audit-logs', {
    params: queryParams,
  });
  return response.data;
}
