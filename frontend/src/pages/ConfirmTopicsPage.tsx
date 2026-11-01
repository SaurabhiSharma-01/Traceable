import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Stepper } from '../components/layout/Stepper';
import { ExpectedTopic } from '../types';
import { useAnalysisDraft } from '../state/AnalysisDraftContext';

export const ConfirmTopicsPage: React.FC = () => {
  const navigate = useNavigate();
  const { draft, setEntity, setTopics } = useAnalysisDraft();

  // If user opens /topics directly without a draft, redirect to home
  useEffect(() => {
    if (!draft.question || draft.topics.length === 0) {
      navigate('/', { replace: true });
    }
  }, [draft.question, draft.topics.length, navigate]);

  const [currentEntity, setCurrentEntity] = useState(draft.entity || '');
  const [topics, setLocalTopics] = useState<ExpectedTopic[]>(draft.topics || []);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleEntityChange = (val: string) => {
    setCurrentEntity(val);
    setEntity(val.trim() || null);
  };

  const handleTopicLabelChange = (index: number, newLabel: string) => {
    const next = [...topics];
    const key = newLabel
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || `topic_${index + 1}`;
    next[index] = { ...next[index], label: newLabel, key };
    setLocalTopics(next);
    setValidationError(null);
  };

  const handleTopicDescChange = (index: number, newDesc: string) => {
    const next = [...topics];
    next[index] = { ...next[index], description: newDesc };
    setLocalTopics(next);
  };

  const handleImportanceChange = (index: number, imp: number) => {
    const next = [...topics];
    next[index] = { ...next[index], importance: imp };
    setLocalTopics(next);
  };

  const handleCriticalToggle = (index: number) => {
    const next = [...topics];
    next[index] = { ...next[index], is_critical: !next[index].is_critical };
    setLocalTopics(next);
  };

  const handleRemoveTopic = (index: number) => {
    if (topics.length <= 1) {
      setValidationError('You must have at least one expected topic.');
      return;
    }
    const next = topics.filter((_, i) => i !== index);
    setLocalTopics(next);
    setValidationError(null);
  };

  const handleAddTopic = () => {
    if (topics.length >= 10) {
      setValidationError('You can have at most 10 verification topics.');
      return;
    }
    const nextIndex = topics.length + 1;
    const newTopic: ExpectedTopic = {
      key: `custom_topic_${nextIndex}`,
      label: `New Topic ${nextIndex}`,
      importance: 3,
      description: 'What to look for in sources',
      is_critical: false,
    };
    setLocalTopics([...topics, newTopic]);
    setValidationError(null);
  };

  const handleContinue = () => {
    // Validate topics
    if (topics.length === 0) {
      setValidationError('At least one topic is required to detect gaps.');
      return;
    }
    if (topics.length > 10) {
      setValidationError('Maximum of 10 topics allowed.');
      return;
    }
    const hasBlank = topics.some((t) => !t.label.trim());
    if (hasBlank) {
      setValidationError('Topic labels cannot be blank. Please name all topics.');
      return;
    }

    setTopics(topics);
    navigate('/sources');
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-2">
      {/* Stepper */}
      <Stepper currentStep={1} />

      {/* Page Heading & Guidance */}
      <div className="space-y-1.5">
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
          Confirm verification topics
        </h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          Gaps are detected by checking these topics against your sources. Add, edit, or remove topics to
          match what matters most for your decision.
        </p>
      </div>

      {/* Detected Entity & Intent Card */}
      <Card padding="md" className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">
          <div className="md:col-span-2 space-y-1.5">
            <label htmlFor="entity-input" className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
              Identified Target Entity
            </label>
            <input
              id="entity-input"
              type="text"
              value={currentEntity}
              onChange={(e) => handleEntityChange(e.target.value)}
              placeholder="e.g. PM YASASVI Scholarship"
              className="w-full px-3 py-2 text-base font-semibold text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-primary"
            />
            <p className="text-xs text-slate-500">
              Extracted directly from your question. Edit if needed.
            </p>
          </div>

          <div className="space-y-1.5 bg-slate-50 border border-slate-200/80 rounded-lg p-3 text-xs">
            <span className="font-semibold text-slate-600 uppercase tracking-wider block">
              Research Intent
            </span>
            <span className="font-medium text-slate-900 block capitalize">
              {draft.intent || 'General verification'}
            </span>
            {draft.entityType && (
              <span className="inline-block text-[11px] bg-slate-200/70 text-slate-700 px-2 py-0.5 rounded font-medium">
                Type: {draft.entityType}
              </span>
            )}
          </div>
        </div>

        {/* Ambiguity Note if Present */}
        {draft.ambiguityNote && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 flex items-start gap-2">
            <span className="text-amber-600 font-bold">⚠️</span>
            <div>
              <span className="font-semibold">Make sure this is the right entity: </span>
              <span>{draft.ambiguityNote}</span>
            </div>
          </div>
        )}
      </Card>

      {/* Topics List Card */}
      <Card padding="md" className="space-y-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Expected Topics ({topics.length}/10)
            </h2>
            <p className="text-xs text-slate-500">
              Mark critical topics where missing information causes costly delays or penalties.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleAddTopic}
            disabled={topics.length >= 10}
          >
            + Add Topic
          </Button>
        </div>

        {validationError && (
          <div className="rounded-md bg-red-50 border border-red-200 p-2.5 text-xs text-red-800 font-medium">
            {validationError}
          </div>
        )}

        <div className="space-y-3">
          {topics.map((topic, index) => (
            <div
              key={topic.key || index}
              className={`border rounded-lg p-3 transition-colors ${
                topic.is_critical ? 'border-amber-300 bg-amber-50/20' : 'border-slate-200 bg-white'
              }`}
            >
              <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                {/* Topic Label & Description */}
                <div className="flex-1 w-full space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">#{index + 1}</span>
                    <input
                      type="text"
                      value={topic.label}
                      onChange={(e) => handleTopicLabelChange(index, e.target.value)}
                      placeholder="Topic name"
                      className="flex-1 font-semibold text-sm text-slate-900 border-b border-transparent hover:border-slate-300 focus:border-primary focus:outline-none py-0.5"
                    />
                  </div>
                  <input
                    type="text"
                    value={topic.description}
                    onChange={(e) => handleTopicDescChange(index, e.target.value)}
                    placeholder="What to verify (e.g. required certificates and eligibility documents)"
                    className="w-full text-xs text-slate-500 border-b border-transparent hover:border-slate-300 focus:border-primary focus:outline-none py-0.5"
                  />
                </div>

                {/* Controls: Importance, Critical Toggle, Remove */}
                <div className="flex items-center gap-3 sm:gap-4 self-end sm:self-center flex-shrink-0 pt-2 sm:pt-0">
                  {/* Importance Selector (1-5 dots) */}
                  <div className="flex items-center gap-1" title={`Importance: ${topic.importance}/5`}>
                    {[1, 2, 3, 4, 5].map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={() => handleImportanceChange(index, level)}
                        className={`w-3.5 h-3.5 rounded-full transition-colors ${
                          level <= topic.importance
                            ? 'bg-primary hover:bg-primary-dark'
                            : 'bg-slate-200 hover:bg-slate-300'
                        }`}
                        aria-label={`Set importance ${level}`}
                      />
                    ))}
                  </div>

                  {/* Critical Toggle */}
                  <div className="relative group">
                    <button
                      type="button"
                      onClick={() => handleCriticalToggle(index)}
                      className={`text-xs px-2 py-1 rounded-md font-medium border transition-colors ${
                        topic.is_critical
                          ? 'bg-amber-100 text-amber-900 border-amber-300 font-semibold'
                          : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'
                      }`}
                    >
                      {topic.is_critical ? '★ Critical' : 'Normal'}
                    </button>
                    <div className="absolute right-0 top-full mt-1 hidden group-hover:block bg-slate-800 text-white text-[11px] p-2 rounded shadow-lg whitespace-nowrap z-30 pointer-events-none">
                      Errors here are costly (deadline, documents, fees, links)
                    </div>
                  </div>

                  {/* Delete Button */}
                  <button
                    type="button"
                    onClick={() => handleRemoveTopic(index)}
                    className="text-slate-400 hover:text-red-600 transition-colors p-1"
                    title="Remove topic"
                    aria-label="Remove topic"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Navigation Footer */}
      <div className="flex items-center justify-between pt-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => navigate('/')}
        >
          ← Back to Question
        </Button>

        <Button
          type="button"
          size="lg"
          onClick={handleContinue}
        >
          Continue to Sources →
        </Button>
      </div>
    </div>
  );
};

