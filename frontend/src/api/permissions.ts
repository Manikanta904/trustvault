import { apiClient } from './client';
import type { DocumentPermissionDetail, PermissionResponse, PermissionType } from '../types';

export async function listDocumentPermissionsApi(
  documentId: number
): Promise<DocumentPermissionDetail[]> {
  const response = await apiClient.get<DocumentPermissionDetail[]>(
    `/documents/${documentId}/permissions`
  );
  return response.data;
}

export async function grantPermissionApi(
  documentId: number,
  userId: number,
  permissionType: PermissionType
): Promise<PermissionResponse> {
  const response = await apiClient.put<PermissionResponse>(
    `/documents/${documentId}/permissions/${userId}`,
    { permission_type: permissionType }
  );
  return response.data;
}

export async function revokePermissionApi(
  documentId: number,
  userId: number
): Promise<void> {
  await apiClient.delete(`/documents/${documentId}/permissions/${userId}`);
}

export {
  getBulkSummaryApi,
  bulkGrantPermissionsApi,
  bulkRevokePermissionsApi,
} from './documents';

