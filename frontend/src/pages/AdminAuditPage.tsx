import React, { useEffect, useState, useCallback } from 'react';
import { listAuditLogsApi } from '../api/admin';
import { extractErrorMessage } from '../api/client';
import {
  ShieldCheck,
  Filter,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import type { AuditLogItem, AuditOutcome } from '../types';

export const AdminAuditPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [limit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  // Filters state
  const [action, setAction] = useState('');
  const [outcome, setOutcome] = useState<string>('');
  const [actorId, setActorId] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const fetchAuditLogs = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);

    const params: {
      limit: number;
      offset: number;
      action?: string;
      outcome?: string;
      actor_id?: number;
      document_id?: number;
    } = { limit, offset };

    if (action.trim()) params.action = action.trim();
    if (outcome) params.outcome = outcome;
    if (actorId.trim() && parseInt(actorId, 10) > 0) {
      params.actor_id = parseInt(actorId, 10);
    }
    if (documentId.trim() && parseInt(documentId, 10) > 0) {
      params.document_id = parseInt(documentId, 10);
    }

    try {
      const data = await listAuditLogsApi(params);
      setLogs(data.items);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to fetch audit records from the server.'));
    } finally {
      setLoading(false);
    }
  }, [limit, offset, action, outcome, actorId, documentId]);

  useEffect(() => {
    let ignore = false;
    const params: {
      limit: number;
      offset: number;
      action?: string;
      outcome?: string;
      actor_id?: number;
      document_id?: number;
    } = { limit, offset };

    if (action.trim()) params.action = action.trim();
    if (outcome) params.outcome = outcome;
    if (actorId.trim() && parseInt(actorId, 10) > 0) {
      params.actor_id = parseInt(actorId, 10);
    }
    if (documentId.trim() && parseInt(documentId, 10) > 0) {
      params.document_id = parseInt(documentId, 10);
    }

    listAuditLogsApi(params)
      .then((data) => {
        if (!ignore) setLogs(data.items);
      })
      .catch((err) => {
        if (!ignore) setError(extractErrorMessage(err, 'Failed to fetch audit records from the server.'));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [limit, offset, action, outcome, actorId, documentId]);

  const clearFilters = () => {
    setAction('');
    setOutcome('');
    setActorId('');
    setDocumentId('');
    setOffset(0);
  };

  const hasActiveFilters = Boolean(action.trim() || outcome || actorId.trim() || documentId.trim());

  const getOutcomeBadge = (eventOutcome: AuditOutcome) => {
    switch (eventOutcome) {
      case 'success':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Success
          </span>
        );
      case 'denied':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            <XCircle className="w-3 h-3 mr-1" />
            Denied
          </span>
        );
      case 'failure':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertTriangle className="w-3 h-3 mr-1" />
            Failure
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
            {eventOutcome}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-slate-900">Immutable Audit Trail</h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-purple-100 text-purple-800 border border-purple-200">
              Admin Restricted
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Complete cryptographic audit trail of security operations and access denials
          </p>
        </div>

        <button
          onClick={() => fetchAuditLogs()}
          disabled={loading}
          title="Refresh audit events"
          className="p-2 self-start sm:self-auto text-slate-600 hover:text-slate-900 bg-white border border-slate-300 rounded-lg shadow-xs hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}


      {/* Filters Bar */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-4 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`inline-flex items-center px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
                showFilters || hasActiveFilters
                  ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                  : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Filter className="w-3.5 h-3.5 mr-1.5" />
              Audit Filters
              {hasActiveFilters && (
                <span className="ml-1.5 w-2 h-2 rounded-full bg-indigo-600"></span>
              )}
            </button>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
              >
                Clear Filters
              </button>
            )}
          </div>

          <div className="text-xs text-slate-500">
            Showing records {offset + 1} &ndash; {offset + logs.length} (Limit: {limit})
          </div>
        </div>

        {/* Filter inputs */}
        {showFilters && (
          <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">
                Action Type
              </label>
              <select
                value={action}
                onChange={(e) => {
                  setAction(e.target.value);
                  setOffset(0);
                }}
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              >
                <option value="">All Actions</option>
                <option value="login">login</option>
                <option value="document_upload">document_upload</option>
                <option value="document_download">document_download</option>
                <option value="document_read_metadata">document_read_metadata</option>
                <option value="document_update">document_update</option>
                <option value="document_delete">document_delete</option>
                <option value="permission_grant">permission_grant</option>
                <option value="permission_revoke">permission_revoke</option>
                <option value="admin_audit_logs_read">admin_audit_logs_read</option>
                <option value="document_create">document_create</option>
                <option value="document_list">document_list</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">
                Outcome
              </label>
              <select
                value={outcome}
                onChange={(e) => {
                  setOutcome(e.target.value);
                  setOffset(0);
                }}
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              >
                <option value="">All Outcomes</option>
                <option value="success">Success</option>
                <option value="denied">Denied (Unauthorized)</option>
                <option value="failure">Failure (Validation/Error)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">
                Actor User ID
              </label>
              <input
                type="number"
                min="1"
                placeholder="e.g. 1"
                value={actorId}
                onChange={(e) => {
                  setActorId(e.target.value);
                  setOffset(0);
                }}
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">
                Document ID
              </label>
              <input
                type="number"
                min="1"
                placeholder="e.g. 10"
                value={documentId}
                onChange={(e) => {
                  setDocumentId(e.target.value);
                  setOffset(0);
                }}
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              />
            </div>
          </div>
        )}
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-2">
            <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
            <p className="text-xs text-slate-500 font-medium">Querying immutable audit logs...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="py-16 text-center px-4">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3 text-slate-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">No audit events found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              No audit logs matched your query criteria.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-5 py-3">Timestamp (UTC)</th>
                  <th className="px-5 py-3">Event ID</th>
                  <th className="px-5 py-3">Actor</th>
                  <th className="px-5 py-3">Action</th>
                  <th className="px-5 py-3">Document</th>
                  <th className="px-5 py-3">Outcome</th>
                  <th className="px-5 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs font-mono">
                {logs.map((entry) => (
                  <tr
                    key={entry.id}
                    className={`hover:bg-slate-50 transition-colors ${
                      entry.outcome === 'denied' ? 'bg-rose-50/20' : ''
                    }`}
                  >
                    <td className="px-5 py-3.5 text-slate-600 whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 font-bold text-slate-800">
                      #{entry.id}
                    </td>
                    <td className="px-5 py-3.5 text-slate-800 font-semibold">
                      {entry.actor_id !== null ? `User #${entry.actor_id}` : 'System'}
                    </td>
                    <td className="px-5 py-3.5 font-semibold text-indigo-700">
                      {entry.action}
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">
                      {entry.document_id !== null ? `Doc #${entry.document_id}` : '—'}
                    </td>
                    <td className="px-5 py-3.5 font-sans whitespace-nowrap">
                      {getOutcomeBadge(entry.outcome)}
                    </td>
                    <td className="px-5 py-3.5 font-sans text-slate-600 max-w-xs sm:max-w-md truncate">
                      {entry.details || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0 || loading}
            className="inline-flex items-center px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-40 transition-colors"
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Previous
          </button>

          <span className="text-xs text-slate-500 font-medium">
            Offset {offset} &bull; Page {Math.floor(offset / limit) + 1}
          </span>

          <button
            onClick={() => setOffset(offset + limit)}
            disabled={logs.length < limit || loading}
            className="inline-flex items-center px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-40 transition-colors"
          >
            Next
            <ChevronRight className="w-4 h-4 ml-1" />
          </button>
        </div>
      </div>
    </div>
  );
};
