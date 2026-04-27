/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { DataProvider, useDataStore } from './lib/useDataStore';
import { ThemeProvider } from './lib/useTheme';
import { AppLayout } from './components/Layout';
import { DataCenter } from './views/DataCenter';
import { Workbench } from './views/Workbench';
import { HealthCheck } from './views/HealthCheck';
import { FeedbackAnalysis } from './views/FeedbackAnalysis';
import { PlayerSegmentation } from './views/PlayerSegmentation';
import { TouchStrategy } from './views/TouchStrategy';
import { CompetitorAnalysis } from './views/CompetitorAnalysis';
import { AnalysisBoundaries } from './views/AnalysisBoundaries';

function ViewManager() {
  const { status } = useDataStore();
  const [currentView, setCurrentView] = useState(status.totalRecords === 0 ? 'data-center' : 'workbench');

  const renderView = () => {
    switch (currentView) {
      case 'data-center':
        return <DataCenter onChangeView={setCurrentView} />;
      case 'workbench':
        return <Workbench onChangeView={setCurrentView} />;
      case 'health':
        return <HealthCheck />;
      case 'feedback':
        return <FeedbackAnalysis />;
      case 'segmentation':
        return <PlayerSegmentation />;
      case 'strategy':
        return <TouchStrategy />;
      case 'competitor':
        return <CompetitorAnalysis onChangeView={setCurrentView} />;
      case 'info':
        return <AnalysisBoundaries />;
      default:
        return <DataCenter onChangeView={setCurrentView} />;
    }
  };

  return (
    <AppLayout currentView={currentView} onViewChange={setCurrentView}>
      {renderView()}
    </AppLayout>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <DataProvider>
        <ViewManager />
      </DataProvider>
    </ThemeProvider>
  );
}
