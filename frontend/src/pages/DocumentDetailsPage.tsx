import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import {
  getDocumentApi,
  downloadDocumentApi,
  deleteDocumentApi,
  getDocumentActivityApi,
} from '../api/documents';
import { extractErrorMessage } from '../api/client';
import {
  ArrowLeft,
  FileText,
  Download,
  Users,
  Edit3,
  Trash2,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  Activity,
} from 'lucide-react';
import axios from 'axios';
import type { DocumentItem, DocumentActivityItem } from '../types';
import { EditDocumentModal } from '../components/documents/EditDocumentModal';
import { ShareModal } from '../components/documents/ShareModal';
import { DeleteConfirmModal } from '../components/documents/DeleteConfirmModal';
import { DocumentViewer } from '../components/documents/DocumentViewer';

export const DocumentDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [activity, setActivity] = useState<DocumentActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isShareOpen, setIsShareOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const isOwner = document?.owner_id === user?.id;
  const canEdit = isOwner || document?.user_permission === 'edit';

  const fetchActivity = useCallback(async (docId: number) => {
    setActivityLoading(true);
    try {
      const data = await getDocumentActivityApi(docId);
      setActivity(data.items);
    } catch {
      // Non-fatal, activity history is best effort
      setActivity([]);
    } finally {
      setActivityLoading(false);
    }
  }, []);

  const fetchDocument = useCallback(async (showLoading = false) => {
    if (!id) return;
    const docId = parseInt(id, 10);
    if (isNaN(docId)) {
      setError('Invalid document ID.');
      setLoading(false);
      return;
    }

    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await getDocumentApi(docId);
      setDocument(data);
      if (data.owner_id === user?.id) {
        fetchActivity(data.id);
      }
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && (err.response?.status === 404 || err.response?.status === 403)) {
        setError('Document unavailable. Your access may have changed.');
      } else {
        setError(extractErrorMessage(err, 'Unable to load document details.'));
      }
    } finally {
      setLoading(false);
    }
  }, [id, user, fetchActivity]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDocument(true);
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchDocument]);

  const handleDownload = async () => {
    if (!document) return;
    setDownloading(true);
    setActionSuccess(null);
    try {
      await downloadDocumentApi(document.id, document.original_filename);
      setActionSuccess(
        isOwner
          ? 'Original document downloaded successfully.'
          : 'Watermarked document downloaded successfully.'
      );
      if (isOwner) {
        fetchActivity(document.id);
      }
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && (err.response?.status === 404 || err.response?.status === 403)) {
        setError('Download denied: You do not have permission to download this document.');
      } else {
        setError(extractErrorMessage(err, 'Failed to download document.'));
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleDelete = async () => {
    if (!document) return;
    try {
      await deleteDocumentApi(document.id);
      navigate('/documents', { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to delete document.'));
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
        <p className="text-xs text-slate-500 font-medium">Verifying authorization and loading metadata...</p>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4 text-center">
        <div className="w-12 h-12 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center mx-auto mb-3">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">Document Unavailable</h2>
        <p className="text-xs text-slate-600 mt-1 mb-6">
          {error || 'This document does not exist or you do not have permission to view it.'}
        </p>
        <Link
          to="/documents"
          className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Documents
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/documents"
          className="inline-flex items-center text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" />
          Back to Repository
        </Link>

        {isOwner ? (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            You Own This Document
          </span>
        ) : (
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            Shared by {document.owner_name || document.owner_email || 'Document Owner'} (
            {document.user_permission === 'edit' ? 'Can Edit' : 'Read Only'})
          </span>
        )}
      </div>

      {actionSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Main Document Card */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-200 flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div className="flex items-start space-x-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center flex-shrink-0 border border-indigo-100">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">{document.title}</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Original Filename: <span className="font-mono text-slate-700">{document.original_filename}</span>
              </p>
              {document.category && (
                <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                  {document.category}
                </span>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center space-x-2 self-start flex-wrap gap-y-2">
            <button
              onClick={handleDownload}
              disabled={downloading}
              title={isOwner ? 'Download original file (Owner)' : 'Download watermarked PDF copy'}
              className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-xs transition-colors disabled:opacity-50"
            >
              <Download className="w-4 h-4 mr-1.5" />
              {downloading
                ? 'Downloading...'
                : isOwner
                ? 'Download Original'
                : 'Download Watermarked PDF'}
            </button>

            {isOwner && (
              <button
                onClick={() => setIsShareOpen(true)}
                className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 transition-colors shadow-xs"
              >
                <Users className="w-4 h-4 mr-1.5 text-indigo-600" />
                Manage Access
              </button>
            )}

            {canEdit && (
              <button
                onClick={() => setIsEditOpen(true)}
                className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 transition-colors shadow-xs"
              >
                <Edit3 className="w-4 h-4 mr-1.5 text-slate-500" />
                Edit
              </button>
            )}

            {isOwner && (
              <button
                onClick={() => setIsDeleteOpen(true)}
                className="inline-flex items-center px-3.5 py-2 rounded-lg text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-colors"
              >
                <Trash2 className="w-4 h-4 mr-1.5" />
                Delete
              </button>
            )}
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 bg-slate-50/50">
          <div className="p-3.5 bg-white rounded-lg border border-slate-200">
            <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">
              Document ID
            </span>
            <p className="text-sm font-mono font-bold text-slate-900">#{document.id}</p>
          </div>

          <div className="p-3.5 bg-white rounded-lg border border-slate-200">
            <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">
              Document Ownership / Shared by
            </span>
            <p className="text-sm font-semibold text-slate-900 truncate">
              {isOwner
                ? 'You (Owner)'
                : document.owner_name
                ? `${document.owner_name} (${document.owner_email || 'owner'})`
                : document.owner_email || 'Document Owner'}
            </p>
            {!isOwner && (
              <span className="inline-block mt-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                {document.user_permission === 'edit' ? 'Can Edit' : 'Read Only'}
              </span>
            )}
          </div>

          <div className="p-3.5 bg-white rounded-lg border border-slate-200">
            <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">
              File Size
            </span>
            <p className="text-sm font-mono font-bold text-slate-900">
              {formatFileSize(document.size_bytes)} ({document.size_bytes} B)
            </p>
          </div>

          <div className="p-3.5 bg-white rounded-lg border border-slate-200">
            <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">
              Content-Type
            </span>
            <p className="text-xs font-mono font-medium text-slate-700 truncate">
              {document.content_type}
            </p>
          </div>
        </div>

        {/* Description Section */}
        <div className="p-6 border-t border-slate-200 space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Description
          </h3>
          <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
            {document.description || 'No description provided.'}
          </p>
        </div>

        {/* Timestamps */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 text-xs text-slate-500 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <span>Uploaded: {new Date(document.created_at).toLocaleString()}</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Last Modified: {new Date(document.updated_at).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Secure In-Browser PDF Viewer */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Eye className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Document Content Viewer</h2>
          </div>
          <span className="text-xs text-slate-500">
            Authenticated In-Browser Stream • Watermarked
          </span>
        </div>

        <DocumentViewer
          documentId={document.id}
          documentTitle={document.title}
          originalFilename={document.original_filename}
          isOwner={isOwner}
          onDownloadOriginal={handleDownload}
          isDownloading={downloading}
        />
      </div>

      {/* Owner Activity & Download History Panel */}
      {isOwner && (
        <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
          <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-bold text-slate-900">
                Document Activity & Download History
              </h3>
            </div>
            <button
              onClick={() => fetchActivity(document.id)}
              disabled={activityLoading}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer"
            >
              {activityLoading ? 'Refreshing...' : 'Refresh Activity'}
            </button>
          </div>

          <div className="p-4">
            {activityLoading && activity.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500">
                Loading activity history...
              </div>
            ) : activity.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">
                No recipient downloads or views recorded yet for this document.
              </p>
            ) : (
              <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                {activity.map((act) => (
                  <div key={act.id} className="py-2.5 flex items-start justify-between text-xs">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-slate-900">
                          {act.actor_name || act.actor_email || 'Authenticated User'}
                        </span>
                        {act.actor_email && act.actor_name && (
                          <span className="text-[11px] text-slate-500">({act.actor_email})</span>
                        )}
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            act.action === 'document_download'
                              ? 'bg-blue-100 text-blue-700'
                              : act.action === 'document_view'
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {act.action === 'document_download'
                            ? 'Download'
                            : act.action === 'document_view'
                            ? 'Preview'
                            : act.action.replace('document_', '').replace('_', ' ')}
                        </span>
                      </div>
                      {act.details && (
                        <p className="text-[11px] text-slate-500 font-mono mt-0.5">{act.details}</p>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-400 whitespace-nowrap ml-4">
                      {new Date(act.created_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modals */}
      <EditDocumentModal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        document={document}
        onSuccess={(updated) => {
          setDocument(updated);
          setActionSuccess('Metadata updated successfully.');
        }}
      />

      <ShareModal
        isOpen={isShareOpen}
        onClose={() => setIsShareOpen(false)}
        document={document}
        onPermissionChanged={fetchDocument}
      />

      <DeleteConfirmModal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        document={document}
        onConfirm={handleDelete}
      />
    </div>
  );
};

