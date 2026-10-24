import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center px-4 py-12 text-center">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4 border border-indigo-100 shadow-xs">
        <ShieldAlert className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">404</h1>
      <h2 className="text-lg font-bold text-slate-800 mt-1">Resource Not Found</h2>
      <p className="text-xs text-slate-500 mt-2 max-w-sm mb-6">
        The requested path does not exist in TrustVault or is unauthorized under current access control policies.
      </p>
      <Link
        to="/dashboard"
        className="inline-flex items-center px-4 py-2 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-1.5" />
        Return to Dashboard
      </Link>
    </div>
  );
};
