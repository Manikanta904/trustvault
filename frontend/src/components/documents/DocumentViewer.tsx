import React, { useEffect, useState, useRef } from 'react';
import { useAuth } from '../../context/useAuth';
import { viewDocumentApi } from '../../api/documents';
import { extractErrorMessage } from '../../api/client';
import axios from 'axios';
import {
  Shield,
  Download,
  Maximize2,
  Minimize2,
  RefreshCw,
  AlertCircle,
  Eye,
  Lock,
  Loader2,
  Info,
} from 'lucide-react';

interface DocumentViewerProps {
  documentId: number;
  documentTitle?: string;
  originalFilename?: string;
  isOwner: boolean;
  onDownloadOriginal?: () => void;
  isDownloading?: boolean;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  documentId,
  documentTitle,
  isOwner,
  onDownloadOriginal,
  isDownloading = false,
}) => {
  const { user } = useAuth();

  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorType, setErrorType] = useState<'auth' | 'network' | 'server' | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [viewTimestamp, setViewTimestamp] = useState<string>(() => new Date().toLocaleString());
  const [reloadKey, setReloadKey] = useState<number>(0);

  const containerRef = useRef<HTMLDivElement>(null);

  const handleReload = () => {
    setLoading(true);
    setErrorType(null);
    setErrorMessage(null);
    setReloadKey((prev) => prev + 1);
  };

  // Load document on mount or documentId / reloadKey change, and cleanup on unmount
  useEffect(() => {
    let ignore = false;
    let activeUrl: string | null = null;

    viewDocumentApi(documentId)
      .then((blob) => {
        if (ignore) return;
        activeUrl = URL.createObjectURL(blob);
        setBlobUrl(activeUrl);
        setErrorType(null);
        setErrorMessage(null);
        setViewTimestamp(new Date().toLocaleString());
      })
      .catch((err: unknown) => {
        if (ignore) return;
        setBlobUrl(null);

        if (axios.isAxiosError(err)) {
          const status = err.response?.status;
          if (status === 404 || status === 403 || status === 401) {
            // Requirement: For 404/revoked/denied, display generic message without leaking private metadata
            setErrorType('auth');
            setErrorMessage('Document unavailable. Your access may have changed.');
          } else if (err.message === 'Network Error' || !err.response) {
            setErrorType('network');
            setErrorMessage('Unable to connect to the backend server. Please verify your connection.');
          } else {
            setErrorType('server');
            setErrorMessage(extractErrorMessage(err, 'Failed to stream document. Please try again.'));
          }
        } else {
          setErrorType('server');
          setErrorMessage('An unexpected error occurred while loading the document.');
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
      if (activeUrl) {
        URL.revokeObjectURL(activeUrl);
      }
    };
  }, [documentId, reloadKey]);

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;

    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (err) {
      console.warn('Fullscreen toggle failed:', err);
    }
  };

  const utcTimestamp = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  const traceRef = `TRC-${documentId}-${(user?.id || 0).toString(16).toUpperCase()}`;
  const watermarkViewerIdentity = user?.name ? `${user.name} (${user.email})` : user?.email || 'Authenticated User';
  const watermarkText = `TRUSTVAULT SECURE • ${user?.email || 'USER'} • Doc #${documentId}`;
  const watermarkSubText = `UTC: ${utcTimestamp} • Ref: ${traceRef} • CONFIDENTIAL`;

  return (
    <div
      ref={containerRef}
      className={`flex flex-col bg-slate-900 rounded-xl overflow-hidden border border-slate-700 shadow-md transition-all ${
        isFullscreen ? 'fixed inset-0 z-50 rounded-none border-0' : 'w-full'
      }`}
    >
      {/* Top Viewer Control Bar */}
      <div className="bg-slate-950 px-4 py-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 text-slate-200">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-indigo-900/60 border border-indigo-700/50 flex items-center justify-center text-indigo-400 flex-shrink-0">
            <Eye className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-white truncate max-w-[200px] sm:max-w-md">
                {documentTitle || 'Document Viewer'}
              </span>
              {isOwner ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-900/70 text-blue-300 border border-blue-700/60 uppercase tracking-wider">
                  Owner
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-900/70 text-emerald-300 border border-emerald-700/60 uppercase tracking-wider">
                  Shared View
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 flex items-center space-x-1.5 mt-0.5 truncate">
              <Shield className="w-3 h-3 text-indigo-400 flex-shrink-0" />
              <span>Watermarked for {watermarkViewerIdentity}</span>
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2 ml-auto">
          {onDownloadOriginal && (
            <button
              type="button"
              onClick={onDownloadOriginal}
              disabled={isDownloading || loading}
              title={isOwner ? "Download original PDF file" : "Download watermarked PDF copy"}
              className="inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 transition-colors shadow-xs"
            >
              <Download className="w-3.5 h-3.5 mr-1.5" />
              {isDownloading ? 'Downloading...' : isOwner ? 'Download Original' : 'Download Watermarked PDF'}
            </button>
          )}

          {/* Refresh / Retry button */}
          <button
            type="button"
            onClick={handleReload}
            disabled={loading}
            title="Reload document stream"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {/* Fullscreen Toggle */}
          <button
            type="button"
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'View Fullscreen'}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Security Disclaimer Banner */}
      <div className="bg-slate-900/90 px-4 py-1.5 border-b border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
        <div className="flex items-center space-x-1.5 truncate">
          <Lock className="w-3 h-3 text-emerald-400 flex-shrink-0" />
          <span className="truncate">
            Protected in-browser preview • Streamed directly via TrustVault API
          </span>
        </div>
        <div className="hidden sm:flex items-center space-x-1 text-slate-500 text-[10px]">
          <Info className="w-3 h-3 flex-shrink-0" />
          <span>Notice: Visual watermark applied to discourage redistribution</span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="relative w-full flex-1 min-h-[550px] sm:min-h-[700px] bg-slate-950 flex flex-col items-center justify-center overflow-hidden">
        {loading && (
          <div className="py-24 flex flex-col items-center justify-center space-y-3 text-slate-300">
            <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
            <p className="text-xs font-medium text-slate-400">
              Verifying database authorization and streaming document...
            </p>
          </div>
        )}

        {!loading && errorType && (
          <div className="p-8 max-w-md mx-auto text-center space-y-3">
            <div className="w-12 h-12 bg-rose-950/80 border border-rose-800 text-rose-400 rounded-full flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-white">
              {errorType === 'auth' ? 'Document Unavailable' : 'Error Loading Document'}
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              {errorMessage}
            </p>
            <div className="pt-2">
              <button
                type="button"
                onClick={handleReload}
                className="inline-flex items-center px-4 py-2 border border-slate-700 rounded-lg text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Try Again
              </button>
            </div>
          </div>
        )}

        {!loading && !errorType && blobUrl && (
          <div className="relative w-full h-full min-h-[550px] sm:min-h-[700px] flex-1 bg-slate-900">
            {/* Embedded Native PDF Viewer */}
            <iframe
              src={`${blobUrl}#toolbar=0&navpanes=0`}
              title="Protected Document Viewer"
              className="w-full h-full min-h-[550px] sm:min-h-[700px] border-0 bg-white"
            />

            {/* Visible Diagonal Security Watermark Overlay (Phase 4A) */}
            <div
              aria-hidden="true"
              className="absolute inset-0 pointer-events-none select-none z-10 overflow-hidden flex flex-col justify-around opacity-25"
            >
              {[...Array(4)].map((_, rowIndex) => (
                <div
                  key={rowIndex}
                  className="flex justify-around items-center w-[160%] -ml-[30%] py-6 transform -rotate-25"
                >
                  {[...Array(2)].map((_, colIndex) => (
                    <div
                      key={colIndex}
                      className="px-6 py-2.5 text-center text-slate-800 font-mono text-xs sm:text-sm font-extrabold tracking-wider uppercase border border-slate-700/20 rounded-md backdrop-blur-2xs"
                    >
                      <p className="whitespace-nowrap">{watermarkText}</p>
                      <p className="text-[10px] text-slate-700 font-semibold tracking-normal mt-0.5 whitespace-nowrap">
                        {watermarkSubText}
                      </p>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer Security Notice */}
      <div className="bg-slate-950 px-4 py-2 border-t border-slate-800 text-[10px] text-slate-400 flex flex-wrap items-center justify-between gap-2">
        <span>Security policy: Original downloads are restricted to verified document owners.</span>
        <span className="text-slate-400">Session timestamp: {viewTimestamp || 'Active'}</span>
      </div>
    </div>
  );
};
