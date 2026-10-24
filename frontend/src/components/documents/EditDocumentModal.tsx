import React, { useState } from 'react';
import { updateDocumentApi } from '../../api/documents';
import { extractErrorMessage } from '../../api/client';
import { Edit3, X, AlertCircle } from 'lucide-react';
import type { DocumentItem } from '../../types';

interface EditDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentItem | null;
  onSuccess: (updated: DocumentItem) => void;
}

const EditDocumentForm: React.FC<{
  document: DocumentItem;
  onClose: () => void;
  onSuccess: (updated: DocumentItem) => void;
}> = ({ document, onClose, onSuccess }) => {
  const [title, setTitle] = useState(document.title);
  const [description, setDescription] = useState(document.description || '');
  const [category, setCategory] = useState(document.category || '');
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Document title cannot be empty.');
      return;
    }

    setIsUpdating(true);
    setError(null);

    try {
      const updated = await updateDocumentApi(document.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        category: category.trim() || undefined,
      });

      onSuccess(updated);
      onClose();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to update document metadata.'));
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-4">
      {error && (
        <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
          Title
        </label>
        <input
          type="text"
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
          className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
          Category
        </label>
        <input
          type="text"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          maxLength={100}
          placeholder="e.g. Legal, Technical, Finance"
          className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1">
          Description
        </label>
        <textarea
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={5000}
          placeholder="Brief summary..."
          className="block w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
        />
      </div>

      <div className="pt-2 flex items-center justify-end space-x-3 border-t border-slate-100">
        <button
          type="button"
          onClick={onClose}
          disabled={isUpdating}
          className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isUpdating}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
        >
          {isUpdating ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </form>
  );
};

export const EditDocumentModal: React.FC<EditDocumentModalProps> = ({
  isOpen,
  onClose,
  document,
  onSuccess,
}) => {
  if (!isOpen || !document) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden border border-slate-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center space-x-2">
            <Edit3 className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">Edit Metadata</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <EditDocumentForm
          key={document.id}
          document={document}
          onClose={onClose}
          onSuccess={onSuccess}
        />
      </div>
    </div>
  );
};
