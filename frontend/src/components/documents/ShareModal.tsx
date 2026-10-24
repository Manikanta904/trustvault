import React, { useState, useEffect, useCallback, useRef } from 'react';
import { grantPermissionApi, revokePermissionApi, listDocumentPermissionsApi } from '../../api/permissions';
import { searchUsersApi } from '../../api/users';
import { extractErrorMessage } from '../../api/client';
import {
  Users,
  X,
  AlertCircle,
  CheckCircle2,
  Trash2,
  Clock,
  Search,
  Loader2,
  Shield,
  UserCheck,
  User as UserIcon,
} from 'lucide-react';
import type { DocumentItem, DocumentPermissionDetail, PermissionType, UserSearchResult } from '../../types';

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentItem | null;
  onPermissionChanged?: () => void;
}

export const ShareModal: React.FC<ShareModalProps> = ({
  isOpen,
  onClose,
  document,
  onPermissionChanged,
}) => {
  // Existing grants state
  const [grants, setGrants] = useState<DocumentPermissionDetail[]>([]);
  const [loadingGrants, setLoadingGrants] = useState(false);
  const [grantsError, setGrantsError] = useState<string | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Selection & Grant state
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null);
  const [permissionType, setPermissionType] = useState<PermissionType>('read');
  const [isGranting, setIsGranting] = useState(false);
  const [revokingUserId, setRevokingUserId] = useState<number | null>(null);

  // Feedback notifications
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch existing permissions from server
  const loadGrants = useCallback(async (docId: number) => {
    setLoadingGrants(true);
    setGrantsError(null);
    try {
      const data = await listDocumentPermissionsApi(docId);
      setGrants(data);
    } catch (err) {
      setGrantsError(extractErrorMessage(err, 'Failed to load existing permissions.'));
    } finally {
      setLoadingGrants(false);
    }
  }, []);

  const handleClose = () => {
    setSearchQuery('');
    setSearchResults([]);
    setSelectedUser(null);
    setHasSearched(false);
    setSearchError(null);
    setError(null);
    setSuccessMsg(null);
    onClose();
  };

  // On open or document change, load grants
  useEffect(() => {
    if (!isOpen || !document) return;

    let ignore = false;
    listDocumentPermissionsApi(document.id)
      .then((data) => {
        if (!ignore) {
          setGrants(data);
          setGrantsError(null);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setGrantsError(extractErrorMessage(err, 'Failed to load existing permissions.'));
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoadingGrants(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [isOpen, document]);

  // Handle debounced search query
  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    setError(null);
    setSearchError(null);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const trimmed = query.trim();
    if (!trimmed) {
      setSearchResults([]);
      setHasSearched(false);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceTimerRef.current = setTimeout(async () => {
      try {
        const results = await searchUsersApi(trimmed, 10);
        setSearchResults(results);
        setHasSearched(true);
      } catch (err) {
        setSearchError(extractErrorMessage(err, 'Failed to search employees.'));
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
  };

  const handleSelectUser = (user: UserSearchResult) => {
    setSelectedUser(user);
    setSearchQuery('');
    setSearchResults([]);
    setHasSearched(false);
    setError(null);

    // If already granted, pre-select their current permission type
    const existing = grants.find((g) => g.user_id === user.id);
    if (existing) {
      setPermissionType(existing.permission_type);
    } else {
      setPermissionType('read');
    }
  };

  const handleClearSelection = () => {
    setSelectedUser(null);
    setError(null);
  };

  // Grant or update permission
  const handleGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!document || !selectedUser) return;

    setError(null);
    setSuccessMsg(null);
    setIsGranting(true);

    try {
      const result = await grantPermissionApi(document.id, selectedUser.id, permissionType);
      const isUpdate = grants.some((g) => g.user_id === selectedUser.id);
      setSuccessMsg(
        isUpdate
          ? `Updated access: ${selectedUser.name} now has '${result.permission_type}' permission.`
          : `Access granted: ${selectedUser.name} has been granted '${result.permission_type}' permission.`
      );
      setSelectedUser(null);
      await loadGrants(document.id);
      if (onPermissionChanged) onPermissionChanged();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to grant permission. Verify the target account.'));
    } finally {
      setIsGranting(false);
    }
  };

  // Revoke permission
  const handleRevoke = async (targetUserId: number, targetName: string) => {
    if (!document) return;

    setError(null);
    setSuccessMsg(null);
    setRevokingUserId(targetUserId);

    try {
      await revokePermissionApi(document.id, targetUserId);
      setSuccessMsg(`Access revoked for ${targetName}. Revocation took effect immediately on the server.`);
      await loadGrants(document.id);
      if (onPermissionChanged) onPermissionChanged();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to revoke access.'));
    } finally {
      setRevokingUserId(null);
    }
  };

  if (!isOpen || !document) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center space-x-2">
            <Users className="w-5 h-5 text-indigo-600" />
            <h3 className="text-base font-bold text-slate-900">Manage Document Access</h3>
          </div>
          <button
            onClick={handleClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          {/* Document Summary */}
          <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 flex items-start space-x-3">
            <Shield className="w-5 h-5 text-indigo-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Document</p>
              <p className="text-sm font-bold text-slate-900 truncate">{document.title}</p>
              <p className="text-xs text-slate-400">{document.original_filename}</p>
            </div>
          </div>

          {/* Feedback alerts */}
          {error && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
              <span className="flex-1">{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              <span className="flex-1">{successMsg}</span>
            </div>
          )}

          {/* Section: Grant New Permission */}
          <div className="space-y-3.5 border-t border-slate-100 pt-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Share with Employee
            </h4>

            {/* Employee Search Box (shown when no employee selected) */}
            {!selectedUser ? (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-slate-700">
                  Search Employee by Name or Registered Email
                </label>
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="e.g. Alice or alice@company.com"
                    value={searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="block w-full pl-9 pr-9 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
                  />
                  {isSearching && (
                    <Loader2 className="w-4 h-4 text-indigo-600 animate-spin absolute right-3 top-2.5" />
                  )}
                  {searchQuery && !isSearching && (
                    <button
                      type="button"
                      onClick={() => handleSearchChange('')}
                      className="text-slate-400 hover:text-slate-600 absolute right-3 top-2.5"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Search Error State */}
                {searchError && (
                  <p className="text-xs text-rose-600 flex items-center space-x-1">
                    <AlertCircle className="w-3.5 h-3.5 mr-1" />
                    {searchError}
                  </p>
                )}

                {/* Search Results Dropdown List */}
                {searchResults.length > 0 && (
                  <div className="border border-slate-200 rounded-lg max-h-48 overflow-y-auto divide-y divide-slate-100 bg-white shadow-xs">
                    {searchResults.map((emp) => {
                      const existingGrant = grants.find((g) => g.user_id === emp.id);
                      return (
                        <button
                          key={emp.id}
                          type="button"
                          onClick={() => handleSelectUser(emp)}
                          className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-indigo-50/70 transition-colors group"
                        >
                          <div className="flex items-center space-x-2.5 min-w-0">
                            <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs flex-shrink-0">
                              {emp.name.charAt(0).toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-slate-900 truncate group-hover:text-indigo-900">
                                {emp.name}
                              </p>
                              <p className="text-[11px] text-slate-500 truncate">{emp.email}</p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-1.5 flex-shrink-0 ml-2">
                            {existingGrant && (
                              <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-100 text-emerald-800 font-medium">
                                Has {existingGrant.permission_type}
                              </span>
                            )}
                            <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-100 text-slate-600 uppercase font-medium">
                              {emp.role}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* No-Results State */}
                {hasSearched && !isSearching && searchResults.length === 0 && searchQuery.trim() !== '' && (
                  <div className="p-3 text-center border border-dashed border-slate-200 rounded-lg text-xs text-slate-500 bg-slate-50">
                    No active employees found matching &ldquo;{searchQuery}&rdquo;.
                  </div>
                )}
              </div>
            ) : (
              /* Selected Employee Card */
              <div className="p-3.5 rounded-lg border border-indigo-200 bg-indigo-50/60 flex items-center justify-between">
                <div className="flex items-center space-x-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">
                    <UserCheck className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-slate-900 truncate">
                        {selectedUser.name}
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] bg-indigo-100 text-indigo-800 font-semibold uppercase">
                        {selectedUser.role}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 truncate">{selectedUser.email}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleClearSelection}
                  className="text-xs text-indigo-700 hover:text-indigo-900 font-medium underline ml-2 flex-shrink-0"
                >
                  Change
                </button>
              </div>
            )}

            {/* Form when user is selected */}
            {selectedUser && (
              <form onSubmit={handleGrant} className="space-y-3.5 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Permission Level
                  </label>
                  <div className="grid grid-cols-2 gap-2.5">
                    <button
                      type="button"
                      onClick={() => setPermissionType('read')}
                      className={`p-2.5 text-left rounded-lg border transition-all ${
                        permissionType === 'read'
                          ? 'border-indigo-600 bg-indigo-50/80 ring-1 ring-indigo-600'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-900">Read Access</span>
                        {permissionType === 'read' && (
                          <span className="w-2 h-2 rounded-full bg-indigo-600" />
                        )}
                      </div>
                      <p className="text-[11px] text-slate-500 leading-tight">
                        View document details and download file content.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setPermissionType('edit')}
                      className={`p-2.5 text-left rounded-lg border transition-all ${
                        permissionType === 'edit'
                          ? 'border-indigo-600 bg-indigo-50/80 ring-1 ring-indigo-600'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-900">Edit Access</span>
                        {permissionType === 'edit' && (
                          <span className="w-2 h-2 rounded-full bg-indigo-600" />
                        )}
                      </div>
                      <p className="text-[11px] text-slate-500 leading-tight">
                        Read, download, and update title/metadata.
                      </p>
                    </button>
                  </div>
                </div>

                <div className="flex items-center space-x-2 pt-1">
                  <button
                    type="submit"
                    disabled={isGranting}
                    className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
                  >
                    {isGranting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                        Saving Permission...
                      </>
                    ) : grants.some((g) => g.user_id === selectedUser.id) ? (
                      'Update Permission'
                    ) : (
                      'Grant Access'
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={handleClearSelection}
                    className="px-3 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Section: Existing Document Grants */}
          <div className="border-t border-slate-100 pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Current Access Grants ({grants.length})
              </h4>
              {loadingGrants && <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />}
            </div>

            {grantsError && (
              <p className="text-xs text-rose-600 flex items-center">
                <AlertCircle className="w-3.5 h-3.5 mr-1 flex-shrink-0" />
                {grantsError}
              </p>
            )}

            {!loadingGrants && grants.length === 0 && !grantsError && (
              <div className="p-4 text-center rounded-lg border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-500">
                <UserIcon className="w-5 h-5 mx-auto text-slate-300 mb-1" />
                No external permissions granted yet. This document is strictly private to you.
              </div>
            )}

            {grants.length > 0 && (
              <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                {grants.map((grant) => (
                  <div
                    key={grant.id}
                    className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-slate-50 text-xs hover:border-slate-300 transition-colors"
                  >
                    <div className="min-w-0 flex-1 mr-2">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-slate-900 truncate">
                          {grant.user_name}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                            grant.permission_type === 'edit'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          {grant.permission_type}
                        </span>
                      </div>
                      <p className="text-slate-500 text-[11px] truncate">{grant.user_email}</p>
                      <p className="text-slate-400 text-[10px] flex items-center mt-0.5">
                        <Clock className="w-3 h-3 mr-1" />
                        Granted {new Date(grant.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRevoke(grant.user_id, grant.user_name)}
                      disabled={revokingUserId === grant.user_id || isGranting}
                      title="Revoke Permission immediately"
                      className="inline-flex items-center px-2 py-1 border border-rose-200 text-rose-700 hover:bg-rose-50 rounded text-xs font-semibold transition-colors disabled:opacity-50 flex-shrink-0"
                    >
                      {revokingUserId === grant.user_id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5 mr-1" />
                      )}
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 text-right">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 rounded-lg transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
