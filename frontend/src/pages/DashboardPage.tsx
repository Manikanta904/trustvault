import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/useAuth';
import { listDocumentsApi, downloadDocumentApi } from '../api/documents';
import { listAuditLogsApi } from '../api/admin';
import { extractErrorMessage } from '../api/client';
import {
  Files,
  FileCheck,
  Users,
  HardDrive,
  UploadCloud,
  Download,
  AlertCircle,
  Eye,
  BarChart3,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FolderOpen,
} from 'lucide-react';
import type { DocumentItem, AuditLogItem } from '../types';
import { Link } from 'react-router-dom';
import { UploadModal } from '../components/documents/UploadModal';
import { ShareModal } from '../components/documents/ShareModal';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [adminLogs, setAdminLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [adminLogsLoading, setAdminLogsLoading] = useState(user?.role === 'admin');
  const [error, setError] = useState<string | null>(null);

  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [shareDoc, setShareDoc] = useState<DocumentItem | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const loadDocuments = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await listDocumentsApi({ limit: 100 });
      setDocuments(data);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to load documents.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    listDocumentsApi({ limit: 100 })
      .then((data) => {
        if (!ignore) setDocuments(data);
      })
      .catch((err) => {
        if (!ignore) setError(extractErrorMessage(err, 'Failed to load documents.'));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    // If user is admin, fetch recent authorized audit activity
    if (user?.role === 'admin') {
      listAuditLogsApi({ limit: 5 })
        .then((resp) => {
          if (!ignore) setAdminLogs(resp.items);
        })
        .catch(() => {
          // Non-critical on dashboard
        })
        .finally(() => {
          if (!ignore) setAdminLogsLoading(false);
        });
    }

    return () => {
      ignore = true;
    };
  }, [user?.role]);

  const handleDownload = async (doc: DocumentItem) => {
    setDownloadingId(doc.id);
    try {
      await downloadDocumentApi(doc.id, doc.original_filename);
    } catch (err) {
      alert(extractErrorMessage(err, 'Failed to download document.'));
    } finally {
      setDownloadingId(null);
    }
  };

  const ownedDocs = documents.filter((d) => d.owner_id === user?.id);
  const sharedDocs = documents.filter((d) => d.owner_id !== user?.id);
  const totalBytes = documents.reduce((acc, curr) => acc + (curr.size_bytes || 0), 0);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  // Compute real category breakdown from loaded documents
  const categoryCounts = documents.reduce<Record<string, number>>((acc, doc) => {
    const cat = doc.category?.trim() || 'General / Uncategorized';
    acc[cat] = (acc[cat] || 0) + 1;
    return acc;
  }, {});

  const categoryEntries = Object.entries(categoryCounts).sort((a, b) => b[1] - a[1]);

  const renderOutcomeBadge = (outcome: string) => {
    switch (outcome) {
      case 'success':
        return (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3 h-3 mr-0.5" /> Success
          </span>
        );
      case 'denied':
        return (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-800">
            <XCircle className="w-3 h-3 mr-0.5" /> Denied
          </span>
        );
      case 'failure':
        return (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-800">
            <AlertTriangle className="w-3 h-3 mr-0.5" /> Failure
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700">
            {outcome}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Welcome Banner */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">
            Welcome back, {user?.name}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage your documents, access controls, and repository activity.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {user?.role === 'owner' && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-colors cursor-pointer"
            >
              <UploadCloud className="w-4 h-4 mr-2" />
              Upload Document
            </button>
          )}
          <Link
            to="/documents"
            className="inline-flex items-center px-4 py-2 rounded-lg text-xs sm:text-sm font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 shadow-2xs transition-colors"
          >
            <Files className="w-4 h-4 mr-2 text-slate-500" />
            Browse Repository
          </Link>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-rose-500 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Metrics Row (Derived strictly from verified API data) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Accessible
            </span>
            <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Files className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{documents.length}</p>
          <p className="text-xs text-slate-400 mt-1">Authorized for this account</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              My Documents
            </span>
            <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <FileCheck className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{ownedDocs.length}</p>
          <p className="text-xs text-slate-400 mt-1">Created by your account</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Shared with Me
            </span>
            <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{sharedDocs.length}</p>
          <p className="text-xs text-slate-400 mt-1">Granted by other owners</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Accessible Storage
            </span>
            <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <HardDrive className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{formatFileSize(totalBytes)}</p>
          <p className="text-xs text-slate-400 mt-1">Total private file volume</p>
        </div>
      </div>

      {/* Middle Section: Document Distribution & Role-Specific Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document Categories Distribution Card (Real data from loaded documents) */}
        <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 lg:col-span-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <BarChart3 className="w-4 h-4 text-indigo-600" />
                <h2 className="text-sm font-bold text-slate-900">Document Categories</h2>
              </div>
              <span className="text-xs text-slate-400">
                {categoryEntries.length} {categoryEntries.length === 1 ? 'category' : 'categories'}
              </span>
            </div>

            {loading ? (
              <div className="py-8 text-center text-xs text-slate-400">Calculating categories...</div>
            ) : categoryEntries.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                <FolderOpen className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                No documents or categories available.
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {categoryEntries.map(([catName, count]) => {
                  const percentage = documents.length > 0 ? Math.round((count / documents.length) * 100) : 0;
                  return (
                    <div key={catName} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium text-slate-700 truncate max-w-[180px]">{catName}</span>
                        <span className="text-slate-400 font-mono">
                          {count} ({percentage}%)
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-indigo-600 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-400">
            Real category distribution of currently accessible repository files.
          </div>
        </div>

        {/* Right Section: Admin Audit Activity OR Role Navigation Guide */}
        <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 lg:col-span-2">
          {user?.role === 'admin' ? (
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-purple-600" />
                  <h2 className="text-sm font-bold text-slate-900">Recent Administrative Audit Activity</h2>
                </div>
                <Link
                  to="/admin/audit"
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-700"
                >
                  View Full Audit Log &rarr;
                </Link>
              </div>

              {adminLogsLoading ? (
                <div className="py-8 text-center text-xs text-slate-400">Loading audit records...</div>
              ) : adminLogs.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No recent audit activity recorded.
                </div>
              ) : (
                <div className="divide-y divide-slate-100 mt-2">
                  {adminLogs.map((log) => (
                    <div key={log.id} className="py-2.5 flex items-center justify-between text-xs gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-slate-900 font-mono text-[11px]">
                            {log.action}
                          </span>
                          {renderOutcomeBadge(log.outcome)}
                        </div>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">
                          {log.details || 'Security event logged'}
                        </p>
                      </div>
                      <div className="text-right flex-shrink-0 text-[11px] text-slate-400">
                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h2 className="text-sm font-bold text-slate-900">Repository Quick Actions</h2>
                <span className="text-xs text-slate-400 capitalize">Role: {user?.role}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                <Link
                  to="/documents"
                  className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-indigo-300 transition-colors group block"
                >
                  <Files className="w-5 h-5 text-indigo-600 mb-1.5" />
                  <h3 className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                    Document Repository
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Search and filter all authorized files in your vault.
                  </p>
                </Link>

                <Link
                  to="/shared"
                  className="p-4 rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-indigo-300 transition-colors group block"
                >
                  <Users className="w-5 h-5 text-emerald-600 mb-1.5" />
                  <h3 className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                    Shared with Me
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    View files shared directly with you by other owners.
                  </p>
                </Link>
              </div>

              {user?.role === 'owner' && (
                <div className="mt-4 p-3 rounded-lg bg-indigo-50/60 border border-indigo-100 text-xs text-indigo-900 flex items-center justify-between">
                  <span>Need to share a document? Open any owned file to manage permissions.</span>
                  <button
                    onClick={() => setIsUploadOpen(true)}
                    className="font-semibold text-indigo-700 hover:text-indigo-800 underline ml-2 whitespace-nowrap cursor-pointer"
                  >
                    Upload New
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Recent Documents Table */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">Recent Documents</h3>
            <p className="text-xs text-slate-500">Authorized files available in your repository</p>
          </div>
          <Link
            to="/documents"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-700"
          >
            View All ({documents.length}) &rarr;
          </Link>
        </div>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-2">
            <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
            <p className="text-xs text-slate-500 font-medium">Loading documents from repository...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="py-12 text-center px-4">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3 text-slate-400">
              <Files className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-slate-900">No documents found</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              You haven't uploaded any documents yet and no documents have been shared with your account.
            </p>
            {user?.role === 'owner' && (
              <button
                onClick={() => setIsUploadOpen(true)}
                className="mt-4 inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors cursor-pointer"
              >
                <UploadCloud className="w-4 h-4 mr-1.5" />
                Upload Your First Document
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-3">Document Title</th>
                  <th className="px-6 py-3">Category</th>
                  <th className="px-6 py-3">File Size</th>
                  <th className="px-6 py-3">Created</th>
                  <th className="px-6 py-3">Ownership</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {documents.slice(0, 5).map((doc) => {
                  const isOwner = doc.owner_id === user?.id;
                  return (
                    <tr key={doc.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-6 py-3.5">
                        <div className="font-semibold text-slate-900 truncate max-w-xs">
                          {doc.title}
                        </div>
                        <div className="text-xs text-slate-400 truncate max-w-xs">
                          {doc.original_filename}
                        </div>
                      </td>
                      <td className="px-6 py-3.5">
                        {doc.category ? (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                            {doc.category}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-3.5 text-xs text-slate-600 font-mono">
                        {formatFileSize(doc.size_bytes)}
                      </td>
                      <td className="px-6 py-3.5 text-xs text-slate-500">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-3.5">
                        {isOwner ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">
                            Owner
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                            Shared with You
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-3.5 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          onClick={() => handleDownload(doc)}
                          disabled={downloadingId === doc.id}
                          title="Download File"
                          className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center cursor-pointer"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        {isOwner && (
                          <button
                            onClick={() => setShareDoc(doc)}
                            title="Manage Permissions"
                            className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center cursor-pointer"
                          >
                            <Users className="w-4 h-4" />
                          </button>
                        )}
                        <Link
                          to={`/documents/${doc.id}`}
                          title="View Details"
                          className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          loadDocuments();
        }}
      />

      {/* Share Modal */}
      <ShareModal
        isOpen={!!shareDoc}
        onClose={() => setShareDoc(null)}
        document={shareDoc}
        onPermissionChanged={loadDocuments}
      />
    </div>
  );
};
