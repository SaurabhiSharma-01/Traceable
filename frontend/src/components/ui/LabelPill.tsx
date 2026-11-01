import React from 'react';

export type LabelVariant = 'sourced' | 'gap' | 'conflict' | 'uncertain' | 'ai';

export interface LabelPillProps {
  variant: LabelVariant;
  label?: string;
  className?: string;
}

export const LabelPill: React.FC<LabelPillProps> = ({
  variant,
  label,
  className = '',
}) => {
  const styles: Record<LabelVariant, { bg: string; text: string; border: string; defaultText: string }> = {
    sourced: {
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-300',
      defaultText: 'SOURCED',
    },
    gap: {
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      border: 'border-amber-300',
      defaultText: 'POTENTIAL GAP',
    },
    conflict: {
      bg: 'bg-rose-50',
      text: 'text-rose-700',
      border: 'border-rose-300',
      defaultText: 'POSSIBLE CONFLICT',
    },
    uncertain: {
      bg: 'bg-slate-100',
      text: 'text-slate-700',
      border: 'border-slate-300',
      defaultText: 'UNCERTAIN',
    },
    ai: {
      bg: 'bg-indigo-50',
      text: 'text-indigo-700',
      border: 'border-indigo-300',
      defaultText: 'AI-GENERATED',
    },
  };

  const current = styles[variant] || styles.uncertain;
  const displayText = label || current.defaultText;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold tracking-wide border ${current.bg} ${current.text} ${current.border} ${className}`}
    >
      {displayText}
    </span>
  );
};

