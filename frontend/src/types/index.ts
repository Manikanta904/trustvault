export type UserRole = 'admin' | 'owner' | 'viewer';

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface DocumentItem {
  id: number;
  title: string;
  description: string | null;
  category: string | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  owner_id: number;
  owner_name?: string | null;
  owner_email?: string | null;
  user_permission?: 'owner' | 'edit' | 'read' | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentCreatePayload {
  title: string;
  description?: string;
  category?: string;
  original_filename: string;
  content_type?: string;
  size_bytes?: number;
}

export interface DocumentUpdatePayload {
  title?: string;
  description?: string;
  category?: string;
}

export type PermissionType = 'read' | 'edit';

export interface PermissionGrantPayload {
  permission_type: PermissionType;
}

export interface PermissionResponse {
  document_id: number;
  user_id: number;
  permission_type: PermissionType;
}

export type AuditOutcome = 'success' | 'denied' | 'failure';

export interface AuditLogItem {
  id: number;
  actor_id: number | null;
  document_id: number | null;
  action: string;
  outcome: AuditOutcome;
  details: string | null;
  created_at: string;
}

export interface AuditLogsResponse {
  items: AuditLogItem[];
  limit: number;
  offset: number;
}

export interface DocumentFilterParams {
  search?: string;
  owner_id?: number;
  owner_search?: string;
  category?: string;
  date_from?: string; // YYYY-MM-DD
  date_to?: string;   // YYYY-MM-DD
  limit?: number;
  offset?: number;
}

export interface AuditLogFilterParams {
  action?: string;
  outcome?: string;
  actor_id?: number;
  document_id?: number;
  start_date?: string; // ISO string
  end_date?: string;   // ISO string
  limit?: number;
  offset?: number;
}

export interface UserSearchResult {
  id: number;
  name: string;
  email: string;
  role: UserRole;
}

export interface DocumentPermissionDetail {
  id: number;
  document_id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  permission_type: PermissionType;
  created_at: string;
}

export interface BulkPermissionGrantPayload {
  permission_type: PermissionType;
}

export interface BulkPermissionResponse {
  document_id: number;
  permission_type: PermissionType;
  affected_count: number;
}

export interface BulkSummaryResponse {
  document_id: number;
  eligible_count: number;
  new_grant_count: number;
  existing_grant_count: number;
}

export interface BulkRevokeResponse {
  document_id: number;
  revoked_count: number;
}

export interface DocumentActivityItem {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  actor_email: string | null;
  action: string;
  outcome: string;
  details: string | null;
  created_at: string;
}

export interface DocumentActivityResponse {
  document_id: number;
  items: DocumentActivityItem[];
}
