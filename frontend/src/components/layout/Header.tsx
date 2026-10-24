import React from 'react';
import { Menu, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { Link, useLocation } from 'react-router-dom';

interface HeaderProps {
  setMobileOpen: (open: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({ setMobileOpen }) => {
  const { user } = useAuth();
  const location = useLocation();

  const getPageTitle = (pathname: string): { title: string; subtitle: string } => {
    if (pathname === '/' || pathname === '/dashboard') {
      return {
        title: 'Security Dashboard',
        subtitle: 'Real-time overview of documents, permissions, and vault status',
      };
    }
    if (pathname.startsWith('/documents')) {
      return {
        title: 'Document Repository',
        subtitle: 'Securely manage, upload, and inspect authorized private files',
      };
    }
    if (pathname === '/shared') {
      return {
        title: 'Shared Documents',
        subtitle: 'Documents shared with you with read or edit permissions',
      };
    }
    if (pathname === '/admin/audit') {
      return {
        title: 'Audit Trail & Integrity Log',
        subtitle: 'Immutable record of security-critical actions and access attempts',
      };
    }
    if (pathname === '/profile') {
      return {
        title: 'User Profile & Security',
        subtitle: 'Account details and session role authorization',
      };
    }
    return { title: 'TrustVault', subtitle: 'Secure Document Vault' };
  };

  const { title, subtitle } = getPageTitle(location.pathname);

  return (
    <header className="sticky top-0 z-10 bg-white border-b border-slate-200 px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between shadow-xs">
      <div className="flex items-center space-x-3">
        {/* Mobile menu trigger */}
        <button
          onClick={() => setMobileOpen(true)}
          className="lg:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h2 className="text-lg sm:text-xl font-bold text-slate-900 leading-tight">
            {title}
          </h2>
          <p className="hidden sm:block text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>

      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Profile Link */}
        {user && (
          <Link
            to="/profile"
            className="flex items-center space-x-2 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-semibold flex items-center justify-center text-xs border border-indigo-200">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="hidden xl:block text-left text-xs">
              <span className="block font-medium text-slate-800">{user.name}</span>
              <span className="block text-slate-500 capitalize">{user.role}</span>
            </div>
            <UserIcon className="w-4 h-4 text-slate-400 xl:hidden" />
          </Link>
        )}
      </div>
    </header>
  );
};
