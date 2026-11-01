import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { understand } from '../api/understand';
import { ApiError } from '../api/client';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { LabelPill } from '../components/ui/LabelPill';
import { Spinner } from '../components/ui/Spinner';
import { useAnalysisDraft } from '../state/AnalysisDraftContext';

const EXAMPLE_PROMPTS = [
  'What should I verify before applying for the PM YASASVI scholarship?',
  'What do I need to check before applying to a central university admission?',
  'What are the eligibility and renewal conditions for the National Overseas Scholarship?',
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { draft, setQuestion, setInitialUnderstanding } = useAnalysisDraft();

  const [inputQuestion, setInputQuestion] = useState(draft.question || '');
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [clarificationNotice, setClarificationNotice] = useState<string | null>(null);

  const charCount = inputQuestion.trim().length;
  const isInputValid = charCount >= 3 && charCount <= 500;

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!isInputValid || loading) return;

    setLoading(true);
    setApiError(null);
    setClarificationNotice(null);

    try {
      const result = await understand(inputQuestion.trim());

      if (result.needs_clarification) {
        setClarificationNotice(
          result.clarification_question ||
            'Please specify which exact scheme, organization, or program you would like to verify.',
        );
        setLoading(false);
        return;
      }

      setInitialUnderstanding(
        inputQuestion.trim(),
        result.entity,
        result.entity_type,
        result.intent,
        result.ambiguity_note,
        result.expected_topics,
      );

      navigate('/topics');
    } catch (err: any) {
      if (err instanceof ApiError) {
        setApiError(err.message);
      } else {
        setApiError('Unable to connect to the server. Please check your backend service.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChipClick = (promptText: string) => {
    setInputQuestion(promptText);
    setQuestion(promptText);
    setClarificationNotice(null);
    setApiError(null);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-12 py-4">
      {/* Hero Section */}
      <section className="text-center space-y-4 pt-4">
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
          Find what the sources aren’t telling you.
        </h1>
        <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
          Enter a research question to examine real web sources. Traceable surfaces missing
          information, side-by-side conflicts, and outdated details — with every finding linked to a
          verbatim quote.
        </p>
      </section>

      {/* Main Question Input Card */}
      <Card className="shadow-md border-slate-200" padding="lg">
        <form onSubmit={handleSubmit} className="space-y-4">
          <label htmlFor="question-input" className="block text-sm font-semibold text-slate-800">
            What decision or program are you researching?
          </label>

          <div className="relative">
            <textarea
              id="question-input"
              rows={3}
              disabled={loading}
              value={inputQuestion}
              onChange={(e) => {
                setInputQuestion(e.target.value);
                setQuestion(e.target.value);
                if (clarificationNotice) setClarificationNotice(null);
              }}
              onKeyDown={handleKeyDown}
              placeholder="e.g. What should I verify before applying for the PM YASASVI scholarship?"
              className="w-full p-3.5 text-sm sm:text-base border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-primary disabled:bg-slate-50 disabled:text-slate-500 resize-none transition"
              maxLength={500}
            />

            {/* Character Count Hint */}
            <div className="flex justify-between items-center text-xs text-slate-400 mt-1.5 px-0.5">
              <span>Press <kbd className="bg-slate-100 border border-slate-200 px-1 py-0.5 rounded font-mono text-[10px]">Enter</kbd> to submit, <kbd className="bg-slate-100 border border-slate-200 px-1 py-0.5 rounded font-mono text-[10px]">Shift+Enter</kbd> for a new line</span>
              <span className={charCount > 500 ? 'text-red-500 font-bold' : ''}>
                {charCount} / 500 chars
              </span>
            </div>
          </div>

          {/* Clarification Notice if Entity Unclear */}
          {clarificationNotice && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-3.5 text-sm text-amber-900 flex items-start gap-2.5">
              <span className="text-amber-600 font-bold">ℹ️</span>
              <div>
                <p className="font-semibold">Clarification needed</p>
                <p className="mt-0.5 text-amber-800">{clarificationNotice}</p>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {apiError && (
            <ErrorBanner
              message={apiError}
              onRetry={handleSubmit}
            />
          )}

          {/* Action Row */}
          <div className="flex items-center justify-between pt-2">
            <div className="text-xs text-slate-500 hidden sm:block">
              Free to test • Real web search & source verification
            </div>
            <Button
              type="submit"
              size="lg"
              loading={loading}
              disabled={!isInputValid || loading}
              className="w-full sm:w-auto"
            >
              {loading ? <Spinner size="sm" label="Understanding your question..." /> : 'Continue to Topics →'}
            </Button>
          </div>
        </form>

        {/* Example Prompt Chips */}
        <div className="mt-6 pt-5 border-t border-slate-100">
          <p className="text-xs font-semibold text-slate-500 mb-2.5 uppercase tracking-wider">
            Example research questions:
          </p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_PROMPTS.map((promptText, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleChipClick(promptText)}
                className="text-xs bg-slate-100 hover:bg-slate-200/80 text-slate-700 py-1.5 px-3 rounded-full transition-colors border border-slate-200/60 text-left"
              >
                {promptText}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Honest Trust Line */}
      <div className="bg-slate-100/70 border border-slate-200/70 rounded-xl p-4 text-center text-xs text-slate-600 max-w-2xl mx-auto">
        <p className="font-medium text-slate-700">
          Every finding links to a source quote. Quotes are verified directly against source text. AI suggestions are always clearly labelled.
        </p>
      </div>

      {/* How it Works Section */}
      <section id="how-it-works" className="space-y-6 pt-6 border-t border-slate-200">
        <div className="text-center space-y-1">
          <h2 className="text-xl font-bold text-slate-900">How Traceable Works</h2>
          <p className="text-sm text-slate-500">
            A transparent four-step pipeline that evaluates evidence rather than claiming absolute truth.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card padding="sm" className="space-y-1.5">
            <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">Step 1</span>
            <h3 className="font-semibold text-sm text-slate-900">Collect real sources</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Searches for official portals, recent updates, and relevant reporting. Never relies on demo data.
            </p>
          </Card>

          <Card padding="sm" className="space-y-1.5">
            <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">Step 2</span>
            <h3 className="font-semibold text-sm text-slate-900">Extract verified quotes</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Finds facts topic-by-topic. Python verifies that every quote is an exact substring of the cited passage.
            </p>
          </Card>

          <Card padding="sm" className="space-y-1.5">
            <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">Step 3</span>
            <h3 className="font-semibold text-sm text-slate-900">Detect gaps & conflicts</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Pinpoints unanswered questions, compares conflicting dates or terms side-by-side, and flags stale pages.
            </p>
          </Card>

          <Card padding="sm" className="space-y-1.5">
            <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">Step 4</span>
            <h3 className="font-semibold text-sm text-slate-900">Verify-next checklist</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Builds a ranked action list prioritized by risk, directing you to confirm critical details on official pages.
            </p>
          </Card>
        </div>

        {/* Label Legend */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-2">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Evidence Label Legend:
          </p>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <LabelPill variant="sourced" />
              <span className="text-slate-600">Verified quote found in source text</span>
            </div>
            <div className="flex items-center gap-1.5">
              <LabelPill variant="gap" />
              <span className="text-slate-600">Not found in any source reviewed</span>
            </div>
            <div className="flex items-center gap-1.5">
              <LabelPill variant="conflict" />
              <span className="text-slate-600">Two sources report differing values</span>
            </div>
            <div className="flex items-center gap-1.5">
              <LabelPill variant="uncertain" />
              <span className="text-slate-600">Low confidence or unverified quote</span>
            </div>
            <div className="flex items-center gap-1.5">
              <LabelPill variant="ai" />
              <span className="text-slate-600">AI suggestion (no evidence attached)</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

