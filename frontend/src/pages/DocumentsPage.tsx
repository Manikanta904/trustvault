import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/useAuth';
import {
  listDocumentsApi,
  downloadDocumentApi,
  deleteDocumentApi,
} from '../api/documents';
import { extractErrorMessage } from '../api/client';
import axios from 'axios';
import {
  Search,
  Filter,
  UploadCloud,
  Download,
  Users,
  Edit3,
  Trash2,
  Eye,
  RefreshCw,
  AlertCircle,
  FileText,
  Calendar,
  X,
  CheckCircle2,
} from 'lucide-react';
import type { DocumentFilterParams, DocumentItem } from '../types';
import { Link } from 'react-router-dom';
import { UploadModal } from '../components/documents/UploadModal';
import { EditDocumentModal } from '../components/documents/EditDocumentModal';
import { ShareModal } from '../components/documents/ShareModal';
import { DeleteConfirmModal } from '../components/documents/DeleteConfirmModal';

export const DocumentsPage: React.FC = () => {
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filter state
  const [activeTab, setActiveTab] = useState<'all' | 'owned' | 'shared'>('all');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [ownerSearch, setOwnerSearch] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [editingDoc, setEditingDoc] = useState<DocumentItem | null>(null);
  const [sharingDoc, setSharingDoc] = useState<DocumentItem | null>(null);
  const [deletingDoc, setDeletingDoc] = useState<DocumentItem | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params: DocumentFilterParams = {
      limit: 100,
      offset: 0,
    };

    if (search.trim()) params.search = search.trim();
    if (category.trim()) params.category = category.trim();
    if (ownerSearch.trim()) params.owner_search = ownerSearch.trim();
    if (ownerId.trim() && parseInt(ownerId, 10) > 0) {
      params.owner_id = parseInt(ownerId, 10);
    }
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;

    try {
      const data = await listDocumentsApi(params);
      setDocuments(data);
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to fetch documents.'));
    } finally {
      setLoading(false);
    }
  }, [search, category, ownerSearch, ownerId, dateFrom, dateTo]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDocuments();
    }, 300);
    return () => clearTimeout(timer);
  }, [fetchDocuments]);

  const handleDownload = async (doc: DocumentItem) => {
    setDownloadingId(doc.id);
    setActionSuccess(null);
    try {
      await downloadDocumentApi(doc.id, doc.original_filename);
      setActionSuccess(
        doc.owner_id === user?.id
          ? `Downloaded original "${doc.title}".`
          : `Downloaded watermarked copy of "${doc.title}".`
      );
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && (err.response?.status === 404 || err.response?.status === 403)) {
        setError('Download denied: You are not authorized to download this document.');
      } else {
        setError(extractErrorMessage(err, 'Download failed.'));
      }
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (doc: DocumentItem) => {
    setActionSuccess(null);
    try {
      await deleteDocumentApi(doc.id);
      setActionSuccess(`Document "${doc.title}" was permanently removed.`);
      fetchDocuments();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to delete document. Only the owner can delete.'));
    }
  };

  const clearFilters = () => {
    setSearch('');
    setCategory('');
    setOwnerSearch('');
    setOwnerId('');
    setDateFrom('');
    setDateTo('');
  };

  const hasActiveFilters = Boolean(
    search.trim() || category.trim() || ownerSearch.trim() || ownerId.trim() || dateFrom || dateTo
  );

  const displayedDocs = documents.filter((d) => {
    if (activeTab === 'owned') return d.owner_id === user?.id;
    if (activeTab === 'shared') return d.owner_id !== user?.id;
    return true;
  });

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Document Repository</h1>
          <p className="text-xs text-slate-500 mt-1">
            Browse, search, and manage files under server-side authorization
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => fetchDocuments()}
            disabled={loading}
            title="Refresh repository"
            className="p-2 text-slate-600 hover:text-slate-900 bg-white border border-slate-300 rounded-lg shadow-xs hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {user?.role === 'owner' && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-colors"
            >
              <UploadCloud className="w-4 h-4 mr-2" />
              Upload Document
            </button>
          )}
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            <span>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

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

      {/* Tabs and Search Controls */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-4 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Tabs */}
          <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg self-start">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                activeTab === 'all'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              All Accessible ({documents.length})
            </button>
            <button
              onClick={() => setActiveTab('owned')}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                activeTab === 'owned'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              My Documents ({documents.filter((d) => d.owner_id === user?.id).length})
            </button>
            <button
              onClick={() => setActiveTab('shared')}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                activeTab === 'shared'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Shared with Me ({documents.filter((d) => d.owner_id !== user?.id).length})
            </button>
          </div>

          {/* Search Input & Filter Toggle */}
          <div className="flex items-center space-x-2 w-full md:w-auto">
            <div className="relative flex-1 md:w-72">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Search className="w-4 h-4" />
              </div>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by title or filename..."
                className="block w-full pl-9 pr-8 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-slate-400 hover:text-slate-600"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`inline-flex items-center px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                showFilters || hasActiveFilters
                  ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                  : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Filter className="w-3.5 h-3.5 mr-1.5" />
              Filters
              {hasActiveFilters && (
                <span className="ml-1.5 w-2 h-2 rounded-full bg-indigo-600"></span>
              )}
            </button>
          </div>
        </div>

        {/* Expandable Advanced Filters */}
        {showFilters && (
          <div className="pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">
                Category
              </label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g. Compliance, Legal"
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1">
                Owner Name or Email
              </label>
              <input
                type="text"
                value={ownerSearch}
                onChange={(e) => setOwnerSearch(e.target.value)}
                placeholder="e.g. Alice or alice@example.com"
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" />
                Date From
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" />
                Date To
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="block w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white text-slate-900"
              />
            </div>

            {hasActiveFilters && (
              <div className="sm:col-span-2 lg:col-span-4 flex justify-end">
                <button
                  type="button"
                  onClick={clearFilters}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold"
                >
                  Clear all active filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center space-y-2">
            <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
            <p className="text-xs text-slate-500 font-medium">Filtering authorized documents...</p>
          </div>
        ) : displayedDocs.length === 0 ? (
          <div className="py-16 text-center px-4">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-3 text-slate-400">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">No documents found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {hasActiveFilters
                ? 'No documents matched the applied filters. Try broadening your search or clearing date ranges.'
                : 'No documents are currently available under this tab.'}
            </p>
            {hasActiveFilters ? (
              <button
                onClick={clearFilters}
                className="mt-4 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 transition-colors"
              >
                Clear Filters
              </button>
            ) : (
              user?.role === 'owner' && (
                <button
                  onClick={() => setIsUploadOpen(true)}
                  className="mt-4 inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
                >
                  <UploadCloud className="w-4 h-4 mr-1.5" />
                  Upload Document
                </button>
              )
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-3">Document Title</th>
                  <th className="px-6 py-3">Category</th>
                  <th className="px-6 py-3">Shared by / Owner</th>
                  <th className="px-6 py-3">Size</th>
                  <th className="px-6 py-3">Created</th>
                  <th className="px-6 py-3">Ownership</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {displayedDocs.map((doc) => {
                  const isOwner = doc.owner_id === user?.id;
                  const canEdit = isOwner || doc.user_permission === 'edit';
                  return (
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
                      <td className="px-6 py-4">
                        {doc.category ? (
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                            {doc.category}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-xs font-medium text-slate-800">
                          {isOwner ? 'You' : (doc.owner_name || `User #${doc.owner_id}`)}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate max-w-[150px]">
                          {isOwner ? user?.email : (doc.owner_email || '')}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-xs font-mono text-slate-600">
                        {formatFileSize(doc.size_bytes)}
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4">
                        {isOwner ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-100 text-blue-800">
                            Owner
                          </span>
                        ) : (
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                            doc.user_permission === 'edit'
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-emerald-100 text-emerald-800'
                          }`}>
                            {doc.user_permission === 'edit' ? 'Shared (Editor)' : 'Shared (Viewer)'}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right space-x-1.5 whitespace-nowrap">
                        {/* Single clear View action */}
                        <Link
                          to={`/documents/${doc.id}`}
                          title="View Document"
                          className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>

                        {/* Download: Owner gets original; shared recipient gets watermarked copy */}
                        <button
                          onClick={() => handleDownload(doc)}
                          disabled={downloadingId === doc.id}
                          title={isOwner ? "Download Original File" : "Download Watermarked PDF"}
                          className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                        >
                          <Download className="w-4 h-4" />
                        </button>

                        {/* Manage Permissions (Owner only) */}
                        {isOwner && (
                          <button
                            onClick={() => setSharingDoc(doc)}
                            title="Manage Access & Permissions"
                            className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                          >
                            <Users className="w-4 h-4" />
                          </button>
                        )}

                        {/* Edit metadata (Owner or editor only) */}
                        {canEdit && (
                          <button
                            onClick={() => setEditingDoc(doc)}
                            title="Edit Metadata"
                            className="p-1.5 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors inline-flex items-center"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                        )}

                        {/* Delete document (Owner only) */}
                        {isOwner && (
                          <button
                            onClick={() => setDeletingDoc(doc)}
                            title="Delete Document"
                            className="p-1.5 text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors inline-flex items-center"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          setActionSuccess('New document successfully uploaded and classified.');
          fetchDocuments();
        }}
      />

      <EditDocumentModal
        isOpen={!!editingDoc}
        onClose={() => setEditingDoc(null)}
        document={editingDoc}
        onSuccess={() => {
          setActionSuccess('Document metadata updated.');
          fetchDocuments();
        }}
      />

      <ShareModal
        isOpen={!!sharingDoc}
        onClose={() => setSharingDoc(null)}
        document={sharingDoc}
        onPermissionChanged={fetchDocuments}
      />

      <DeleteConfirmModal
        isOpen={!!deletingDoc}
        onClose={() => setDeletingDoc(null)}
        document={deletingDoc}
        onConfirm={handleDelete}
      />
    </div>
  );
};
