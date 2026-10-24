import React from 'react';
import { useAuth } from '../context/useAuth';
import {
  Mail,
  CheckCircle2,
  LogOut,
  Files,
  Users,
  ShieldCheck,
  ArrowRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export const ProfilePage: React.FC = () => {
  const { user, logout } = useAuth();

  if (!user) return null;

  const getRoleDescription = (role: string) => {
    switch (role) {
      case 'admin':
        return 'System Administrator with authority to inspect compliance records and audit trails.';
      case 'owner':
        return 'Document Owner authorized to upload, manage, edit, and share private files.';
      case 'viewer':
        return 'Document Viewer authorized to read and download documents shared with this account.';
      default:
        return 'Standard User';
    }
  };

  const getRoleBadgeClasses = (role: string) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'owner':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'viewer':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Account Profile</h1>
        <p className="text-xs text-slate-500 mt-1">
          Review your account details and role permissions
        </p>
      </div>

      {/* Profile Overview Card */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 overflow-hidden">
        <div className="p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100">
          <div className="flex items-center space-x-4">
            <div className="w-14 h-14 rounded-2xl bg-indigo-600 text-white font-bold text-xl flex items-center justify-center shadow-md shadow-indigo-600/20">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">{user.name}</h2>
              <div className="flex items-center space-x-2 text-xs text-slate-500 mt-0.5">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                <span>{user.email}</span>
              </div>
            </div>
          </div>

          <button
            onClick={logout}
            className="inline-flex items-center px-4 py-2 rounded-lg text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-colors self-start sm:self-auto cursor-pointer"
          >
            <LogOut className="w-4 h-4 mr-1.5" />
            Sign Out
          </button>
        </div>

        {/* Identity & Status Details */}
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4 bg-slate-50/50">
          <div className="p-4 bg-white rounded-lg border border-slate-200">
            <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">
              Account Status
            </span>
            <span className="inline-flex items-center text-xs font-semibold text-emerald-700">
              <CheckCircle2 className="w-4 h-4 mr-1 text-emerald-500" />
              Active
            </span>
          </div>

          <div className="p-4 bg-white rounded-lg border border-slate-200">
            <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">
              Assigned Role
            </span>
            <span
              className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider border ${getRoleBadgeClasses(
                user.role
              )}`}
            >
              {user.role}
            </span>
          </div>
        </div>

        {/* Role Overview */}
        <div className="p-6 border-t border-slate-200 space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Role Permissions
          </h3>
          <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200">
            {getRoleDescription(user.role)}
          </p>
        </div>
      </div>

      {/* Role-Specific Quick Navigation */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Authorized Sections
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            to="/documents"
            className="p-4 bg-white rounded-xl border border-slate-200 hover:border-indigo-300 hover:shadow-xs transition-all flex items-center justify-between group"
          >
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Files className="w-5 h-5" />
              </div>
              <div>
                <span className="text-xs font-bold text-slate-900 group-hover:text-indigo-600">
                  Document Repository
                </span>
                <p className="text-[11px] text-slate-400">Search and access repository files</p>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-600 transition-colors" />
          </Link>

          {user.role === 'admin' ? (
            <Link
              to="/admin/audit"
              className="p-4 bg-white rounded-xl border border-slate-200 hover:border-purple-300 hover:shadow-xs transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs font-bold text-slate-900 group-hover:text-purple-600">
                    Audit Trail & Logs
                  </span>
                  <p className="text-[11px] text-slate-400">Inspect system access and security events</p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-purple-600 transition-colors" />
            </Link>
          ) : (
            <Link
              to="/shared"
              className="p-4 bg-white rounded-xl border border-slate-200 hover:border-emerald-300 hover:shadow-xs transition-all flex items-center justify-between group"
            >
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs font-bold text-slate-900 group-hover:text-emerald-600">
                    Shared with Me
                  </span>
                  <p className="text-[11px] text-slate-400">View documents shared by other owners</p>
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-emerald-600 transition-colors" />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
};
