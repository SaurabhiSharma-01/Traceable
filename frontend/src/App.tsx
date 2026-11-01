import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AnalysisDraftProvider } from './state/AnalysisDraftContext';
import { AppShell } from './components/layout/AppShell';
import { HomePage } from './pages/HomePage';
import { ConfirmTopicsPage } from './pages/ConfirmTopicsPage';
import { SourcesPlaceholderPage } from './pages/SourcesPlaceholderPage';
import { NotFoundPage } from './pages/NotFoundPage';

export function App() {
  return (
    <BrowserRouter>
      <AnalysisDraftProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/topics" element={<ConfirmTopicsPage />} />
            <Route path="/sources" element={<SourcesPlaceholderPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AppShell>
      </AnalysisDraftProvider>
    </BrowserRouter>
  );
}

export default App;
