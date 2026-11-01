import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAnalysisDraft } from '../state/AnalysisDraftContext';
import { Card, Button, Spinner, ErrorBanner, LabelPill } from '../components';
import { Analysis, Fact, Finding } from '../types';

export const Results = () => {
  const { draft, setDraft } = useAnalysisDraft();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect if no analysis result
  useEffect(() => {
    if (!draft?.analysis) {
      navigate('/');
    }
  }, []);

  const analysis: Analysis | undefined = draft?.analysis;

  if (!analysis) {
    return null;
  }

  const totalTopics = draft?.topics?.length ?? 0;
  const verifiedCount = analysis.findings.filter(f => f.kind === 'summary').length;
  const gapCount = analysis.findings.filter(f => f.kind === 'gap').length;
  const conflictCount = analysis.findings.filter(f => f.kind === 'conflict').length;
  const staleCount = analysis.findings.filter(f => f.kind === 'stale').length;

  return (
    <div className="p-4">
      <header className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-xl font-semibold">{analysis.question}</h2>
          <p className="text-gray-600">{analysis.entity}</p>
        </div>
        <Button onClick={() => navigate('/sources')}>New analysis</Button>
      </header>
      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-3 mb-6">
        <Card>Sources reviewed: {analysis.sources.length}</Card>
        <Card>Topics verified: {verifiedCount} / {totalTopics}</Card>
        <Card>Potential gaps: {gapCount}</Card>
        {conflictCount > 0 && <Card>Possible conflicts: {conflictCount}</Card>}
        {staleCount > 0 && <Card>Stale/Undated sources: {staleCount}</Card>}
      </div>
      {/* Warnings */}
      {analysis.warnings?.length > 0 && (
        <div className="bg-amber-100 text-amber-800 p-2 rounded mb-4">
          {analysis.warnings.map((w, i) => <p key={i}>{w}</p>)}
        </div>
      )}
      {/* Findings tabs - simplified */}
      <div className="mb-6">
        <h3 className="font-medium mb-2">Findings</h3>
        {analysis.findings.map((f, idx) => (
          <Card key={idx} className="mb-2">
            <LabelPill>{f.label}</LabelPill>
            <h4 className="font-medium mt-1">{f.title}</h4>
            <p className="text-sm mt-1">{f.explanation}</p>
            {f.quotes && f.quotes.slice(0, 1).map((q, qIdx) => (
              <blockquote key={qIdx} className="border-l-4 border-gray-300 pl-2 italic mt-2">
                "{q.quote}" – {q.sourceId}
              </blockquote>
            ))}
            <Button className="mt-2" onClick={() => {/* open drawer – omitted for brevity */}}>
              View evidence
            </Button>
          </Card>
        ))}
      </div>
      {/* Disclaimer */}
      <p className="text-xs text-gray-500 mt-8">
        AI-generated signals, not guaranteed facts. Verify with official sources.
      </p>
    </div>
  );
};

