import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

export const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="max-w-md mx-auto my-16 text-center space-y-4">
      <Card padding="lg">
        <h1 className="text-4xl font-extrabold text-slate-900">404</h1>
        <p className="text-sm text-slate-500 mt-2 mb-6">
          The requested page was not found.
        </p>
        <Button onClick={() => navigate('/')}>Return to Home</Button>
      </Card>
    </div>
  );
};

