import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAnalysisDraft } from '../state/AnalysisDraftContext';
import { postApi } from '../api/client';
import { Card, Button, Spinner, ErrorBanner, LabelPill } from '../components';
import { SourceCandidate, SourceManual } from '../types';

export const Sources = () => {
  const { draft, setDraft } = useAnalysisDraft();
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<SourceCandidate[]>([]);
  const [manualUrls, setManualUrls] = useState('');
  const [manualTexts, setManualTexts] = useState({ title: '', text: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  // redirect if no draft
  useEffect(() => {
    if (!draft?.entity || !draft?.topics?.length) {
      navigate('/');
    } else {
      fetchCandidates();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchCandidates = async () => {
    try {
      const resp = await postApi('/api/sources/search', {
        entity: draft!.entity,
        topics: draft!.topics.map(t => t.key),
      });
      setCandidates(resp.candidates);
      setWarnings(resp.warnings ?? []);
    } catch (e: any) {
      setError(e.message || 'Failed to search sources');
    }
  };

  const toggleCandidate = (id: string) => {
    setCandidates(prev =>
      prev.map(c => (c.id === id ? { ...c, selected: !c.selected } : c))
    );
  };

  const canAddMore =
    candidates.filter(c => c.selected).length + manualUrls.split('\n').filter(u => u).length < 5;

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    const selectedIds = candidates.filter(c => c.selected).map(c => c.id);
    const urls = [...selectedIds.map(id => candidates.find(c => c.id === id)!.url),
      ...manualUrls.split('\n').filter(u => u)];
    const texts = manualTexts.title && manualTexts.text ? [{ title: manualTexts.title, text: manualTexts.text }] : [];
    try {
      const analysis = await postApi('/api/analyze', {
        question: draft!.question,
        entity: draft!.entity,
        topics: draft!.topics,
        urls,
        texts,
      }, { timeout: 180000 });
      setDraft(prev => ({ ...prev!, analysis }));
      navigate('/results');
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      {error && <ErrorBanner message={error} retry={fetchCandidates} />}
      {warnings.map((w, i) => (
        <div key={i} className="bg-amber-100 text-amber-800 p-2 rounded mb-2">
          {w}
        </div>
      ))}
      <h2 className="text-xl font-semibold mb-2">Choose sources</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {candidates.slice(0, 4).map(c => (
          <Card key={c.id} className="relative">
            <input
              type="checkbox"
              checked={c.selected}
              onChange={() => toggleCandidate(c.id)}
              className="absolute top-2 left-2"
            />
            <h3 className="font-medium">{c.title}</h3>
            <p className="text-sm text-gray-600">{c.domain}</p>
            <LabelPill>{c.classification}</LabelPill>
            <p className="mt-2 text-sm line-clamp-3">{c.snippet}</p>
          </Card>
        ))}
      </div>
      <div className="mt-6">
        <h3 className="font-medium">Add URLs (one per line)</h3>
        <textarea
          value={manualUrls}
          onChange={e => setManualUrls(e.target.value)}
          rows={3}
          className="w-full border rounded p-2"
          disabled={!canAddMore}
        />
        <h3 className="font-medium mt-4">Paste text</h3>
        <input
          placeholder="Title"
          value={manualTexts.title}
          onChange={e => setManualTexts({ ...manualTexts, title: e.target.value })}
          className="w-full border rounded p-2 mb-2"
        />
        <textarea
          placeholder="Text"
          value={manualTexts.text}
          onChange={e => setManualTexts({ ...manualTexts, text: e.target.value })}
          rows={4}
          className="w-full border rounded p-2"
        />
        <p className="mt-2 text-sm text-gray-600">
          Sources selected: {candidates.filter(c => c.selected).length + manualUrls.split('\n').filter(u => u).length} / 5
        </p>
        <Button
          onClick={runAnalysis}
          disabled={loading || !canAddMore}
          className="mt-4"
        >
          {loading ? <Spinner /> : 'Run analysis'}
        </Button>
      </div>
    </div>
  );
};

