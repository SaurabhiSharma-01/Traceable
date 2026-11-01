import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Stepper } from '../components/layout/Stepper';
import { useAnalysisDraft } from '../state/AnalysisDraftContext';

export const SourcesPlaceholderPage: React.FC = () => {
  const navigate = useNavigate();
  const { draft } = useAnalysisDraft();

  return (
    <div className="max-w-4xl mx-auto space-y-8 py-2">
      <Stepper currentStep={2} />

      <Card padding="lg" className="text-center space-y-6 max-w-xl mx-auto my-8">
        <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto text-xl font-bold">
          2
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Sources Step</h1>
          <p className="text-sm text-slate-600">
            Source candidate review, custom URL addition, text pasting, and PDF uploads are coming in the next phase.
          </p>
        </div>

        {draft.entity && (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs text-left space-y-1">
            <p className="font-semibold text-slate-700">Current Research Draft:</p>
            <p className="text-slate-600"><span className="font-medium">Entity:</span> {draft.entity}</p>
            <p className="text-slate-600"><span className="font-medium">Topics:</span> {draft.topics.length} topics confirmed</p>
          </div>
        )}

        <div className="pt-2">
          <Button variant="secondary" onClick={() => navigate('/topics')}>
            ← Back to Confirm Topics
          </Button>
        </div>
      </Card>
    </div>
  );
};

