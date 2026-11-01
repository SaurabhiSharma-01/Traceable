import React, { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAnalysisDraft } from '../../state/AnalysisDraftContext';

export interface AppShellProps {
  children: ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const navigate = useNavigate();
  const { resetDraft } = useAnalysisDraft();

  const handleNewAnalysis = () => {
    resetDraft();
    navigate('/');
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800 font-sans">
      {/* Top Disclaimer Strip */}
      <div className="bg-amber-50/90 border-b border-amber-200/80 px-4 py-1.5 text-center text-xs text-amber-900 font-medium">
        <span className="inline-block mr-1">⚠️</span>
        AI-generated signals, not guaranteed facts. Always verify findings with official sources.
      </div>

      {/* Main Navigation Header */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo & Tagline */}
          <Link
            to="/"
            onClick={handleNewAnalysis}
            className="flex items-center gap-2.5 group focus:outline-none"
          >
            <div className="w-8 h-8 rounded-lg bg-primary text-white flex items-center justify-center font-bold text-lg shadow-sm group-hover:bg-primary-dark transition-colors">
              T
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 tracking-tight block leading-none">
                Traceable
              </span>
              <span className="text-[11px] text-slate-500 font-normal leading-none">
                Every finding, traced to its source
              </span>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="flex items-center gap-4 text-sm font-medium">
            <button
              onClick={handleNewAnalysis}
              className="text-slate-600 hover:text-slate-900 transition-colors py-1 px-2 rounded-md hover:bg-slate-100"
            >
              New Analysis
            </button>

            <a
              href="/#how-it-works"
              className="text-slate-600 hover:text-slate-900 transition-colors py-1 px-2 rounded-md hover:bg-slate-100"
            >
              How it works
            </a>

            {/* Disabled History with Tooltip */}
            <div className="relative group">
              <button
                disabled
                className="text-slate-400 cursor-not-allowed py-1 px-2 rounded-md flex items-center gap-1"
                aria-describedby="history-tooltip"
              >
                History
                <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded border border-slate-200">
                  Soon
                </span>
              </button>
              <div
                id="history-tooltip"
                role="tooltip"
                className="absolute right-0 top-full mt-1.5 hidden group-hover:block bg-slate-800 text-white text-xs px-2.5 py-1.5 rounded shadow-lg whitespace-nowrap z-50 pointer-events-none"
              >
                Available once analyses are saved
              </div>
            </div>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        {children}
      </main>

      {/* Honest Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 mt-16 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 space-y-1.5">
          <p className="font-semibold text-slate-700">Traceable</p>
          <p>Every finding, traced to its source.</p>
          <p className="text-slate-400">
            AI-generated signals, not guaranteed facts. Designed to reveal information gaps and conflicts.
          </p>
        </div>
      </footer>
    </div>
  );
};

