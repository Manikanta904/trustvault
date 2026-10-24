import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  Shield,
  LayoutDashboard,
  Files,
  Users,
  ShieldCheck,
  User as UserIcon,
  LogOut,
  X,
} from 'lucide-react';

interface SidebarProps {
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ mobileOpen, setMobileOpen }) => {
  const { user, logout } = useAuth();

  const navItems = [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: LayoutDashboard,
      roles: ['admin', 'owner', 'viewer'],
    },
    {
      name: 'Documents',
      path: '/documents',
      icon: Files,
      roles: ['admin', 'owner', 'viewer'],
    },
    {
      name: 'Shared with Me',
      path: '/shared',
      icon: Users,
      roles: ['admin', 'owner', 'viewer'],
    },
    {
      name: 'Audit Trail',
      path: '/admin/audit',
      icon: ShieldCheck,
      roles: ['admin'],
    },
    {
      name: 'Profile',
      path: '/profile',
      icon: UserIcon,
      roles: ['admin', 'owner', 'viewer'],
    },
  ];

  const visibleItems = navItems.filter(
    (item) => !user || item.roles.includes(user.role)
  );

  const getRoleBadgeColor = (role?: string) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-900/60 text-purple-300 border-purple-700/50';
      case 'owner':
        return 'bg-blue-900/60 text-blue-300 border-blue-700/50';
      case 'viewer':
        return 'bg-emerald-900/60 text-emerald-300 border-emerald-700/50';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const navContent = (
    <div className="flex flex-col h-full bg-slate-900 text-slate-100 border-r border-slate-800">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center shadow-md shadow-indigo-600/30">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
              TrustVault
            </h1>
            <p className="text-xs text-slate-400 font-medium">Secure Document Vault</p>
          </div>
        </div>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 py-4 space-y-1.5 overflow-y-auto">
        {visibleItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
              }`
            }
          >
            <item.icon className="w-4 h-4 mr-3" />
            {item.name}
            {item.name === 'Audit Trail' && (
              <span className="ml-auto text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                Admin
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User Footer Card */}
      {user && (
        <div className="p-4 border-t border-slate-800 bg-slate-900/80">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-3 overflow-hidden">
              <div className="w-9 h-9 rounded-full bg-indigo-600/30 text-indigo-300 font-bold flex items-center justify-center border border-indigo-500/30 flex-shrink-0">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{user.name}</p>
                <p className="text-xs text-slate-400 truncate">{user.email}</p>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors flex-shrink-0"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
          <div className="flex items-center justify-between pt-1">
            <span
              className={`text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border ${getRoleBadgeColor(
                user.role
              )}`}
            >
              Role: {user.role}
            </span>
            <span className="text-[11px] text-slate-400 font-medium">Active</span>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar (fixed width) */}
      <aside className="hidden lg:flex lg:flex-shrink-0 lg:w-64 z-20">
        <div className="w-64 h-screen fixed inset-y-0 left-0">{navContent}</div>
      </aside>

      {/* Mobile Drawer Backdrop and Sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 max-w-xs w-full shadow-2xl z-50">
            {navContent}
          </div>
        </div>
      )}
    </>
  );
};
