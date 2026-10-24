import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { extractErrorMessage } from '../api/client';
import {
  Shield,
  Lock,
  Mail,
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  ShieldCheck,
  FileCheck2,
  LockKeyhole,
} from 'lucide-react';

// Local demonstration password for testing and evaluation.
// In production builds without explicit VITE_DEMO_PASSWORD configuration,
// this password is not embedded into the production bundle.
const LOCAL_DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD || (import.meta.env.DEV ? '123456789abc' : '');
const isDemoAvailable = import.meta.env.DEV || Boolean(import.meta.env.VITE_DEMO_PASSWORD);

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError('Please enter your email address.');
      return;
    }

    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);
    try {
      await login(trimmedEmail, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, 'Invalid credentials. Please verify your email and password.'));
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (demoEmail: string, demoPassword = LOCAL_DEMO_PASSWORD) => {
    setEmail(demoEmail);
    setPassword(demoPassword);
    setError(null);
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-slate-50">
      {/* Left Panel: Enterprise Branding & Core Value Proposition */}
      <div className="hidden lg:flex lg:w-1/2 bg-slate-900 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 border-r border-slate-800 text-white flex-col justify-between p-12 lg:p-16 relative overflow-hidden">
        {/* Top Branding */}
        <div className="flex items-center space-x-3 z-10">
          <div className="w-11 h-11 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-white block">TrustVault</span>
            <span className="text-xs text-indigo-300 font-medium">Enterprise Document Security</span>
          </div>
        </div>

        {/* Hero Copy & Minimal Capability Highlights */}
        <div className="my-auto py-12 max-w-lg z-10">
          <h1 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Your documents. <br />
            <span className="text-indigo-400">Your control.</span>
          </h1>

          <p className="mt-4 text-sm text-slate-300 leading-relaxed">
            Enterprise document storage engineered with strict server-side authorization,
            granular discretionary access control, and complete audit accountability.
          </p>

          <div className="mt-8 space-y-4">
            <div className="flex items-start space-x-3.5 p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/50 backdrop-blur-xs">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-300 flex items-center justify-center flex-shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold text-white">Server-Enforced Isolation</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Live database authorization checks on every read, download, edit, and deletion request.
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-3.5 p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/50 backdrop-blur-xs">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-300 flex items-center justify-center flex-shrink-0 mt-0.5">
                <LockKeyhole className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold text-white">Controlled Document Sharing</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Granular Read and Edit permission management with instant server-side revocation.
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-3.5 p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/50 backdrop-blur-xs">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-300 flex items-center justify-center flex-shrink-0 mt-0.5">
                <FileCheck2 className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold text-white">Comprehensive Audit Trail</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Append-only historical records tracking authorized actions and unauthorized access attempts.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Platform Tag */}
        <div className="text-xs text-slate-400 flex items-center space-x-2 z-10">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span>Zero-Trust Architecture</span>
        </div>
      </div>

      {/* Right Panel: Sign-In Form & Local Demo Controls */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center items-center px-6 py-12 sm:px-12 lg:px-16">
        <div className="w-full max-w-md space-y-6">
          {/* Mobile Brand Header */}
          <div className="lg:hidden text-center mb-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/30 mb-2">
              <Shield className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">TrustVault</h2>
            <p className="text-xs text-slate-500">Your documents. Your control.</p>
          </div>

          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Sign in to your account
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Enter your credentials to access your document repository.
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1"
              >
                Email Address
              </label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="block w-full pl-9 pr-3 py-2.5 text-xs sm:text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1"
              >
                Password
              </label>
              <div className="relative rounded-lg shadow-2xs">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full pl-9 pr-10 py-2.5 text-xs sm:text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white placeholder-slate-400 text-slate-900"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 focus:outline-hidden"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 flex justify-center items-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-60 transition-colors cursor-pointer"
            >
              {loading ? (
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  <span>Signing In...</span>
                </div>
              ) : (
                <div className="flex items-center space-x-1.5">
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </div>
              )}
            </button>
          </form>

          {/* Quick Fill Demo Accounts (Local Development / Evaluation Only) */}
          {isDemoAvailable && (
            <div className="pt-5 border-t border-slate-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Demonstration Accounts
                </span>
                <span className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded font-medium">
                  Local Demo Only
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mb-3 leading-relaxed">
                Pre-fill local demo credentials for hackathon evaluation (password: <code className="text-slate-700 font-mono text-[10px] bg-slate-100 px-1 py-0.5 rounded">123456789abc</code>).
              </p>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  id="quick-fill-admin"
                  onClick={() => handleQuickFill('admin@example.com', LOCAL_DEMO_PASSWORD)}
                  className="py-2 px-2 text-xs font-semibold rounded-lg border border-purple-200 bg-purple-50 text-purple-700 hover:bg-purple-100 transition-colors text-center cursor-pointer"
                >
                  Admin
                </button>
                <button
                  type="button"
                  id="quick-fill-owner"
                  onClick={() => handleQuickFill('owner@example.com', LOCAL_DEMO_PASSWORD)}
                  className="py-2 px-2 text-xs font-semibold rounded-lg border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors text-center cursor-pointer"
                >
                  Owner
                </button>
                <button
                  type="button"
                  id="quick-fill-viewer"
                  onClick={() => handleQuickFill('viewer@example.com', LOCAL_DEMO_PASSWORD)}
                  className="py-2 px-2 text-xs font-semibold rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors text-center cursor-pointer"
                >
                  Viewer
                </button>
              </div>
            </div>
          )}

          <div className="text-center pt-2">
            <p className="text-xs text-slate-600">
              Don't have an account?{' '}
              <Link to="/register" className="font-semibold text-indigo-600 hover:text-indigo-500">
                Register as Owner
              </Link>
            </p>
          </div>

          {/* User-facing footer */}
          <div className="pt-4 text-center text-xs text-slate-400">
            <p>Secure access to your documents</p>
          </div>
        </div>
      </div>
    </div>
  );
};
