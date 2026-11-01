/**
 * AnalysisDraftContext.tsx — In-memory draft context for ongoing research queries.
 *
 * NOTE: Strictly in-memory per SPEC. Never persisted to localStorage.
 */
import React, { createContext, useContext, useState, ReactNode } from 'react';
import { ExpectedTopic } from '../types';

export interface AnalysisDraft {
  question: string;
  entity: string | null;
  entityType: string | null;
  intent: string;
  ambiguityNote: string | null;
  topics: ExpectedTopic[];
}

interface AnalysisDraftContextType {
  draft: AnalysisDraft;
  setQuestion: (question: string) => void;
  setEntity: (entity: string | null) => void;
  setEntityType: (type: string | null) => void;
  setIntent: (intent: string) => void;
  setTopics: (topics: ExpectedTopic[]) => void;
  updateTopic: (index: number, updated: Partial<ExpectedTopic>) => void;
  addTopic: (topic: ExpectedTopic) => void;
  removeTopic: (index: number) => void;
  setInitialUnderstanding: (
    question: string,
    entity: string | null,
    entityType: string | null,
    intent: string,
    ambiguityNote: string | null,
    topics: ExpectedTopic[],
  ) => void;
  resetDraft: () => void;
}

const defaultDraft: AnalysisDraft = {
  question: '',
  entity: null,
  entityType: null,
  intent: 'pre-application verification',
  ambiguityNote: null,
  topics: [],
};

const AnalysisDraftContext = createContext<AnalysisDraftContextType | undefined>(undefined);

export const AnalysisDraftProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [draft, setDraft] = useState<AnalysisDraft>(defaultDraft);

  const setQuestion = (question: string) => setDraft((d) => ({ ...d, question }));
  const setEntity = (entity: string | null) => setDraft((d) => ({ ...d, entity }));
  const setEntityType = (entityType: string | null) => setDraft((d) => ({ ...d, entityType }));
  const setIntent = (intent: string) => setDraft((d) => ({ ...d, intent }));
  const setTopics = (topics: ExpectedTopic[]) => setDraft((d) => ({ ...d, topics }));

  const updateTopic = (index: number, updated: Partial<ExpectedTopic>) => {
    setDraft((d) => {
      const next = [...d.topics];
      if (next[index]) {
        next[index] = { ...next[index], ...updated };
      }
      return { ...d, topics: next };
    });
  };

  const addTopic = (topic: ExpectedTopic) => {
    setDraft((d) => ({ ...d, topics: [...d.topics, topic] }));
  };

  const removeTopic = (index: number) => {
    setDraft((d) => ({
      ...d,
      topics: d.topics.filter((_, i) => i !== index),
    }));
  };

  const setInitialUnderstanding = (
    question: string,
    entity: string | null,
    entityType: string | null,
    intent: string,
    ambiguityNote: string | null,
    topics: ExpectedTopic[],
  ) => {
    setDraft({
      question,
      entity,
      entityType,
      intent,
      ambiguityNote,
      topics,
    });
  };

  const resetDraft = () => setDraft(defaultDraft);

  return (
    <AnalysisDraftContext.Provider
      value={{
        draft,
        setQuestion,
        setEntity,
        setEntityType,
        setIntent,
        setTopics,
        updateTopic,
        addTopic,
        removeTopic,
        setInitialUnderstanding,
        resetDraft,
      }}
    >
      {children}
    </AnalysisDraftContext.Provider>
  );
};

export function useAnalysisDraft() {
  const context = useContext(AnalysisDraftContext);
  if (!context) {
    throw new Error('useAnalysisDraft must be used within an AnalysisDraftProvider');
  }
  return context;
}

