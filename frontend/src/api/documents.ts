import { apiClient } from './client';
import type {
  BulkPermissionResponse,
  BulkRevokeResponse,
  BulkSummaryResponse,
  DocumentActivityResponse,
  DocumentFilterParams,
  DocumentItem,
  DocumentUpdatePayload,
  PermissionType,
} from '../types';

export interface UploadMetadata {
  title?: string;
  description?: string;
  category?: string;
}

export async function listDocumentsApi(params?: DocumentFilterParams): Promise<DocumentItem[]> {
  const queryParams: Record<string, string | number> = {};
  if (params?.search) queryParams.search = params.search;
  if (params?.owner_id) queryParams.owner_id = params.owner_id;
  if (params?.owner_search) queryParams.owner_search = params.owner_search;
  if (params?.category) queryParams.category = params.category;
  if (params?.date_from) queryParams.date_from = params.date_from;
  if (params?.date_to) queryParams.date_to = params.date_to;
  if (params?.limit) queryParams.limit = params.limit;
  if (params?.offset !== undefined) queryParams.offset = params.offset;

  const response = await apiClient.get<DocumentItem[]>('/documents', {
    params: queryParams,
  });
  return response.data;
}

export async function getDocumentApi(id: number): Promise<DocumentItem> {
  const response = await apiClient.get<DocumentItem>(`/documents/${id}`);
  return response.data;
}

export async function uploadDocumentApi(
  file: File,
  metadata?: UploadMetadata,
  onUploadProgress?: (progressEvent: { loaded: number; total?: number }) => void
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('file', file);
  if (metadata?.title) formData.append('title', metadata.title);
  if (metadata?.description) formData.append('description', metadata.description);
  if (metadata?.category) formData.append('category', metadata.category);

  // Note: Axios automatically sets multipart/form-data with the correct boundary
  const response = await apiClient.post<DocumentItem>('/documents/upload', formData, {
    onUploadProgress,
  });
  return response.data;
}

export async function updateDocumentApi(
  id: number,
  payload: DocumentUpdatePayload
): Promise<DocumentItem> {
  const response = await apiClient.patch<DocumentItem>(`/documents/${id}`, payload);
  return response.data;
}

export async function deleteDocumentApi(id: number): Promise<void> {
  await apiClient.delete(`/documents/${id}`);
}

export async function downloadDocumentApi(id: number, fallbackFilename = 'document'): Promise<void> {
  const response = await apiClient.get<Blob>(`/documents/${id}/download`, {
    responseType: 'blob',
  });

  // Extract filename from Content-Disposition header if available
  let filename = fallbackFilename;
  const rawDisposition = response.headers['content-disposition'];
  const disposition = typeof rawDisposition === 'string' ? rawDisposition : undefined;
  if (disposition) {
    const filenameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch?.[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '');
    }
  }

  const rawContentType = response.headers['content-type'];
  const contentType = typeof rawContentType === 'string' ? rawContentType : 'application/octet-stream';

  // Create temporary blob URL and trigger browser download
  const blob = new Blob([response.data], {
    type: contentType,
  });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function viewDocumentApi(id: number): Promise<Blob> {
  const response = await apiClient.get<Blob>(`/documents/${id}/view`, {
    responseType: 'blob',
  });
  return response.data;
}

export async function getBulkSummaryApi(documentId: number): Promise<BulkSummaryResponse> {
  const response = await apiClient.get<BulkSummaryResponse>(
    `/documents/${documentId}/permissions/bulk-summary`
  );
  return response.data;
}

export async function bulkGrantPermissionsApi(
  documentId: number,
  permissionType: PermissionType
): Promise<BulkPermissionResponse> {
  const response = await apiClient.post<BulkPermissionResponse>(
    `/documents/${documentId}/permissions/bulk`,
    { permission_type: permissionType }
  );
  return response.data;
}

export async function bulkRevokePermissionsApi(
  documentId: number
): Promise<BulkRevokeResponse> {
  const response = await apiClient.delete<BulkRevokeResponse>(
    `/documents/${documentId}/permissions/bulk`
  );
  return response.data;
}

export async function getDocumentActivityApi(
  documentId: number
): Promise<DocumentActivityResponse> {
  const response = await apiClient.get<DocumentActivityResponse>(
    `/documents/${documentId}/activity`
  );
  return response.data;
}
