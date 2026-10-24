import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/useAuth';
import { listDocumentsApi, downloadDocumentApi } from '../api/documents';
import { extractErrorMessage } from '../api/client';
import {
  Users,
  Download,
  Eye,
  Edit3,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import type { DocumentItem } from '../types';
import { Link } from 'react-router-dom';
import { EditDocumentModal } from '../components/documents/EditDocumentModal';

export const SharedDocumentsPage: React.FC = () => {
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const [editingDoc, setEditingDoc] = useState<DocumentItem | null>(null);

  const fetchSharedDocuments = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const allDocs = await listDocumentsApi({ limit: 100 });
      const shared = allDocs.filter((d) => d.owner_id !== user?.id);
      setDocuments(shared);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to fetch shared documents.'));
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    let ignore = false;
    listDocumentsApi({ limit: 100 })
      .then((allDocs) => {
        if (!ignore) {
          const shared = allDocs.filter((d) => d.owner_id !== user?.id);
          setDocuments(shared);
        }
      })
      .catch((err) => {
        if (!ignore) setError(extractErrorMessage(err, 'Failed to fetch shared documents.'));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [user?.id]);

  const handleDownload = async (doc: DocumentItem) => {
    setDownloadingId(doc.id);
    setActionSuccess(null);
    try {
      await downloadDocumentApi(doc.id, doc.original_filename);
      setActionSuccess(`Downloaded "${doc.title}".`);
    } catch (err) {
      setError(extractErrorMessage(err, 'Download denied. Your grant may have been revoked.'));
      // Immediate revocation verification: re-fetch documents list
      fetchSharedDocuments();
    } finally {
      setDownloadingId(null);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Shared Documents</h1>
          <p className="text-xs text-slate-500 mt-1">
            Documents explicitly shared with you by other vault owners
          </p>
        </div>

        <button
          onClick={() => fetchSharedDocuments()}
          disabled={loading}
          title="Refresh shared list"
          className="p-2 self-start sm:self-auto text-slate-600 hover:text-slate-900 bg-white border border-slate-300 rounded-lg shadow-xs hover:bg-slate-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Documents Table */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-2">
            <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
            <p className="text-xs text-slate-500 font-medium">Checking authorized shared documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="py-16 text-center px-4">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3 text-slate-400">
              <Users className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">No shared documents</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              No documents have been shared with your account yet.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-3">Document Title</th>
                  <th className="px-6 py-3">Owner</th>
                  <th className="px-6 py-3">Category</th>
                  <th className="px-6 py-3">File Size</th>
                  <th className="px-6 py-3">Date Shared</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4">
                      <Link
                        to={`/documents/${doc.id}`}
                        className="font-semibold text-slate-900 hover:text-indigo-600 transition-colors truncate block max-w-xs sm:max-w-md"
                      >
                        {doc.title}
                      </Link>
                      <div className="text-xs text-slate-400 truncate max-w-xs sm:max-w-md">
                        {doc.original_filename}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs font-mono font-medium text-slate-700">
                      User #{doc.owner_id}
                    </td>
                    <td className="px-6 py-4">
                      {doc.category ? (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                          {doc.category}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-xs font-mono text-slate-600">
                      {formatFileSize(doc.size_bytes)}
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-500">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right space-x-1.5 whitespace-nowrap">
                      <button
                        onClick={() => handleDownload(doc)}
                        disabled={downloadingId === doc.id}
                        title="Download Document"
                        className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                      >
                        <Download className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => setEditingDoc(doc)}
                        title="Edit Metadata (Requires Edit Grant)"
                        className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>

                      <Link
                        to={`/documents/${doc.id}`}
                        title="View Details"
                        className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                      >
                        <Eye className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <EditDocumentModal
        isOpen={!!editingDoc}
        onClose={() => setEditingDoc(null)}
        document={editingDoc}
        onSuccess={() => {
          setActionSuccess('Metadata updated successfully.');
          fetchSharedDocuments();
        }}
      />
    </div>
  );
};
