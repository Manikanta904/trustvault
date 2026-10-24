import React, { useState } from 'react';
import { Trash2, AlertTriangle, X } from 'lucide-react';
import type { DocumentItem } from '../../types';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentItem | null;
  onConfirm: (document: DocumentItem) => Promise<void>;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  onClose,
  document,
  onConfirm,
}) => {
  const [loading, setLoading] = useState(false);

  if (!isOpen || !document) return null;

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await onConfirm(document);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full overflow-hidden border border-slate-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-rose-50/50">
          <div className="flex items-center space-x-2 text-rose-600">
            <AlertTriangle className="w-5 h-5" />
            <h3 className="text-base font-bold text-slate-900">Confirm Deletion</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-sm text-slate-700">
            Are you sure you want to delete <span className="font-semibold text-slate-900">"{document.title}"</span>?
          </p>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
            <p className="text-slate-600 font-medium">Filename: {document.original_filename}</p>
            <p className="text-slate-500">Document ID: #{document.id}</p>
          </div>

          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1">
            <span className="font-semibold">Security Compliance Note:</span>
            <p>
              The stored file will be unlinked from private filesystem storage. In compliance with TrustVault audit policy, historical audit trail records will retain the document ID reference.
            </p>
          </div>

          <div className="pt-2 flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={loading}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-rose-600 hover:bg-rose-700 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-rose-500 disabled:opacity-50 transition-colors"
            >
              <Trash2 className="w-4 h-4 mr-1.5" />
              {loading ? 'Deleting...' : 'Delete Document'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
