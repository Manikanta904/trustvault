import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  grantPermissionApi,
  revokePermissionApi,
  listDocumentPermissionsApi,
  getBulkSummaryApi,
  bulkGrantPermissionsApi,
  bulkRevokePermissionsApi,
} from '../../api/permissions';
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
  Globe,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import type {
  DocumentItem,
  DocumentPermissionDetail,
  PermissionType,
  UserSearchResult,
  BulkSummaryResponse,
} from '../../types';

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
  // Navigation tabs: 'individual' vs 'bulk'
  const [activeTab, setActiveTab] = useState<'individual' | 'bulk'>('individual');

  // Existing grants state
  const [grants, setGrants] = useState<DocumentPermissionDetail[]>([]);
  const [loadingGrants, setLoadingGrants] = useState(false);
  const [grantsError, setGrantsError] = useState<string | null>(null);

  // Individual Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Individual Selection & Grant state
  const [selectedUser, setSelectedUser] = useState<UserSearchResult | null>(null);
  const [permissionType, setPermissionType] = useState<PermissionType>('read');
  const [isGranting, setIsGranting] = useState(false);
  const [revokingUserId, setRevokingUserId] = useState<number | null>(null);

  // Bulk Sharing state (Requirement E)
  const [bulkPermissionType, setBulkPermissionType] = useState<PermissionType>('read');
  const [bulkSummary, setBulkSummary] = useState<BulkSummaryResponse | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [isSubmittingBulk, setIsSubmittingBulk] = useState(false);

  // Bulk Revocation state (Requirement F)
  const [showBulkRevokeConfirm, setShowBulkRevokeConfirm] = useState(false);
  const [isBulkRevoking, setIsBulkRevoking] = useState(false);

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
    setBulkSummary(null);
    setSummaryError(null);
    setShowBulkRevokeConfirm(false);
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

  // Handle debounced search query (Requirement D)
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

  // Grant or update individual permission
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

  // Revoke individual permission
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

  // Pre-flight check for bulk sharing (Requirement E)
  const handleFetchBulkSummary = async () => {
    if (!document) return;

    setIsLoadingSummary(true);
    setSummaryError(null);
    setError(null);
    setSuccessMsg(null);

    try {
      const summary = await getBulkSummaryApi(document.id);
      setBulkSummary(summary);
    } catch (err) {
      setSummaryError(extractErrorMessage(err, 'Failed to calculate eligible recipient counts.'));
      setBulkSummary(null);
    } finally {
      setIsLoadingSummary(false);
    }
  };

  // Execute bulk sharing (Requirement E)
  const handleConfirmBulkGrant = async () => {
    if (!document) return;

    setIsSubmittingBulk(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const result = await bulkGrantPermissionsApi(document.id, bulkPermissionType);
      setSuccessMsg(
        `Successfully shared with all employees! ${result.affected_count} active accounts now have '${result.permission_type}' access.`
      );
      setBulkSummary(null);
      await loadGrants(document.id);
      if (onPermissionChanged) onPermissionChanged();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to complete bulk sharing. The transaction was safely rolled back.'));
    } finally {
      setIsSubmittingBulk(false);
    }
  };

  // Execute bulk revocation (Requirement F)
  const handleConfirmBulkRevoke = async () => {
    if (!document) return;

    setIsBulkRevoking(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const result = await bulkRevokePermissionsApi(document.id);
      setSuccessMsg(
        `Bulk revocation complete: Removed access for all ${result.revoked_count} recipient(s). Document is now strictly private.`
      );
      setShowBulkRevokeConfirm(false);
      await loadGrants(document.id);
      if (onPermissionChanged) onPermissionChanged();
    } catch (err) {
      setError(extractErrorMessage(err, 'Failed to revoke shared permissions.'));
    } finally {
      setIsBulkRevoking(false);
    }
  };

  if (!isOpen || !document) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200">
        {/* Modal Header */}
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

        <div className="p-6 space-y-5 max-h-[82vh] overflow-y-auto">
          {/* Document Summary */}
          <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 flex items-start space-x-3">
            <Shield className="w-5 h-5 text-indigo-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Target Document</p>
              <p className="text-sm font-bold text-slate-900 truncate">{document.title}</p>
              <p className="text-xs text-slate-400 truncate">{document.original_filename}</p>
            </div>
          </div>

          {/* Feedback alerts */}
          {error && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
              <span className="flex-1 leading-relaxed">{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              <span className="flex-1 leading-relaxed">{successMsg}</span>
            </div>
          )}

          {/* Tab Selector: Individual vs Bulk */}
          <div className="flex border-b border-slate-200">
            <button
              type="button"
              onClick={() => {
                setActiveTab('individual');
                setError(null);
              }}
              className={`pb-2.5 px-4 text-xs font-bold transition-colors border-b-2 -mb-px flex items-center space-x-1.5 ${
                activeTab === 'individual'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <UserIcon className="w-3.5 h-3.5" />
              <span>Share with Employee</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab('bulk');
                setError(null);
              }}
              className={`pb-2.5 px-4 text-xs font-bold transition-colors border-b-2 -mb-px flex items-center space-x-1.5 ${
                activeTab === 'bulk'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Share with All Employees</span>
            </button>
          </div>

          {/* TAB 1: INDIVIDUAL EMPLOYEE SEARCH & GRANT */}
          {activeTab === 'individual' && (
            <div className="space-y-3.5 pt-1">
              {!selectedUser ? (
                <div className="space-y-2">
                  <label className="block text-xs font-medium text-slate-700">
                    Search Employee by Name or Email
                  </label>
                  <div className="relative">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      placeholder="e.g. Alice or alice@example.com"
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
                          View PDF inside TrustVault. Cannot download original file.
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
                          View PDF and update document metadata. Cannot download original.
                        </p>
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 pt-1">
                    <button
                      type="submit"
                      disabled={isGranting}
                      className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-lg shadow-xs text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 transition-colors"
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
          )}

          {/* TAB 2: BULK SHARING WITH ALL ACTIVE EMPLOYEES (Requirement E) */}
          {activeTab === 'bulk' && (
            <div className="space-y-4 pt-1">
              <div className="p-3.5 rounded-lg bg-indigo-50/60 border border-indigo-200 text-xs text-slate-700 space-y-1.5">
                <p className="font-semibold text-indigo-900 flex items-center space-x-1.5">
                  <Globe className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                  <span>Bulk Organization Sharing</span>
                </p>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Grants document access to all currently active employee accounts in the organization.
                  Document ownership remains strictly with you. Future accounts will not receive automatic access.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Select Permission Level to Grant
                </label>
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => {
                      setBulkPermissionType('read');
                      setBulkSummary(null);
                    }}
                    className={`p-2.5 text-left rounded-lg border transition-all ${
                      bulkPermissionType === 'read'
                        ? 'border-indigo-600 bg-indigo-50/80 ring-1 ring-indigo-600'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-slate-900">Read Access</span>
                      {bulkPermissionType === 'read' && (
                        <span className="w-2 h-2 rounded-full bg-indigo-600" />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 leading-tight">
                      In-browser viewing only. Original downloads restricted.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setBulkPermissionType('edit');
                      setBulkSummary(null);
                    }}
                    className={`p-2.5 text-left rounded-lg border transition-all ${
                      bulkPermissionType === 'edit'
                        ? 'border-indigo-600 bg-indigo-50/80 ring-1 ring-indigo-600'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-slate-900">Edit Access</span>
                      {bulkPermissionType === 'edit' && (
                        <span className="w-2 h-2 rounded-full bg-indigo-600" />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 leading-tight">
                      Viewing plus metadata updates. Cannot manage sharing.
                    </p>
                  </button>
                </div>
              </div>

              {/* Pre-flight summary button or preview card */}
              {!bulkSummary ? (
                <div>
                  <button
                    type="button"
                    onClick={handleFetchBulkSummary}
                    disabled={isLoadingSummary}
                    className="w-full inline-flex items-center justify-center px-4 py-2.5 border border-indigo-600 rounded-lg shadow-xs text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 disabled:opacity-50 transition-colors"
                  >
                    {isLoadingSummary ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                        Calculating Eligible Employees...
                      </>
                    ) : (
                      <>
                        <Users className="w-3.5 h-3.5 mr-1.5" />
                        Preview Impact & Review Recipients
                        <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                      </>
                    )}
                  </button>
                  {summaryError && (
                    <p className="text-xs text-rose-600 mt-2 flex items-center">
                      <AlertCircle className="w-3.5 h-3.5 mr-1 flex-shrink-0" />
                      {summaryError}
                    </p>
                  )}
                </div>
              ) : (
                /* Confirmation Card with Backend Stats */
                <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50/40 space-y-3.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-indigo-950 uppercase tracking-wide">
                      Bulk Sharing Impact Preview
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-600 text-white uppercase">
                      {bulkPermissionType} access
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2.5 rounded-lg bg-white border border-indigo-100">
                      <p className="text-lg font-extrabold text-indigo-600 font-mono">
                        {bulkSummary.eligible_count}
                      </p>
                      <p className="text-[10px] text-slate-500 font-semibold uppercase mt-0.5">
                        Eligible Employees
                      </p>
                    </div>
                    <div className="p-2.5 rounded-lg bg-white border border-indigo-100">
                      <p className="text-lg font-extrabold text-emerald-600 font-mono">
                        {bulkSummary.new_grant_count}
                      </p>
                      <p className="text-[10px] text-slate-500 font-semibold uppercase mt-0.5">
                        New Grants
                      </p>
                    </div>
                    <div className="p-2.5 rounded-lg bg-white border border-indigo-100">
                      <p className="text-lg font-extrabold text-amber-600 font-mono">
                        {bulkSummary.existing_grant_count}
                      </p>
                      <p className="text-[10px] text-slate-500 font-semibold uppercase mt-0.5">
                        Will Be Updated
                      </p>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-white border border-indigo-200 text-xs text-slate-700 leading-relaxed space-y-1">
                    <p className="font-semibold text-slate-900">
                      This will grant <span className="uppercase text-indigo-700 font-bold">{bulkPermissionType}</span> access to {bulkSummary.eligible_count} active employees.
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Note: Counts reflect eligible active accounts at preview time. The backend transaction re-validates eligibility at execution time.
                    </p>
                  </div>

                  <div className="flex items-center space-x-2 pt-1">
                    <button
                      type="button"
                      onClick={handleConfirmBulkGrant}
                      disabled={isSubmittingBulk || bulkSummary.eligible_count === 0}
                      className="flex-1 inline-flex items-center justify-center px-4 py-2.5 border border-transparent rounded-lg shadow-xs text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                    >
                      {isSubmittingBulk ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                          Executing Bulk Grant...
                        </>
                      ) : (
                        `Confirm & Share with All (${bulkSummary.eligible_count})`
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => setBulkSummary(null)}
                      disabled={isSubmittingBulk}
                      className="px-3.5 py-2.5 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Section: Existing Document Grants & Bulk Revocation */}
          <div className="border-t border-slate-200 pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center space-x-1.5">
                <span>Current Access Grants</span>
                <span className="px-1.5 py-0.2 rounded-full bg-slate-200 text-slate-700 text-[10px] font-bold">
                  {grants.length}
                </span>
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

            {/* Bulk Revocation Action (Requirement F) */}
            {grants.length > 0 && !showBulkRevokeConfirm && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowBulkRevokeConfirm(true)}
                  disabled={loadingGrants || isBulkRevoking}
                  className="w-full inline-flex items-center justify-center px-3 py-2 border border-rose-300 rounded-lg text-xs font-bold text-rose-700 bg-rose-50/70 hover:bg-rose-100 hover:border-rose-400 transition-colors shadow-2xs"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5 text-rose-600" />
                  Revoke All Shared Access ({grants.length})
                </button>
              </div>
            )}

            {/* Bulk Revoke Confirmation Dialog */}
            {showBulkRevokeConfirm && (
              <div className="p-4 rounded-xl border border-rose-300 bg-rose-50/90 space-y-3">
                <div className="flex items-start space-x-2.5">
                  <ShieldAlert className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <h5 className="text-xs font-bold text-rose-900">
                      Confirm Bulk Revocation
                    </h5>
                    <p className="text-[11px] text-rose-800 leading-relaxed">
                      This will immediately revoke access for all <strong>{grants.length} shared recipient(s)</strong>.
                      They will immediately lose access to view and edit this document in TrustVault.
                    </p>
                    <p className="text-[10px] text-rose-700 font-medium">
                      Notice: Your ownership remains intact. Files previously downloaded outside TrustVault cannot be erased remotely.
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2 pt-1">
                  <button
                    type="button"
                    onClick={handleConfirmBulkRevoke}
                    disabled={isBulkRevoking}
                    className="flex-1 inline-flex items-center justify-center px-3.5 py-2 border border-transparent rounded-lg text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 disabled:opacity-50 transition-colors shadow-xs"
                  >
                    {isBulkRevoking ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                        Revoking All Grants...
                      </>
                    ) : (
                      'Yes, Revoke All Shared Access'
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => setShowBulkRevokeConfirm(false)}
                    disabled={isBulkRevoking}
                    className="px-3.5 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <span className="text-[11px] text-slate-400">
            Permissions are evaluated and audited in real time
          </span>
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
