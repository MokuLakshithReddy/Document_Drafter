import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ConfirmModal } from './components/ConfirmModal';
import { UploadModal } from './features/upload/UploadModal';
import { ReviewView } from './features/review/ReviewView';
import { LibraryView } from './features/library/LibraryView';
import { GenerationModal } from './features/generation/GenerationModal';
import { ResultsModal } from './features/results/ResultsModal';
import { SettingsView } from './features/settings/SettingsView';
import type {
  TemplateSummary,
  TemplateDetail,
  AnalysisResult,
  GenerationJob,
  AppSettings,
  VariableItem,
  Occurrence
} from './types';
import { api } from './api/client';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<'library' | 'review' | 'settings'>('library');
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [recentGenerations, setRecentGenerations] = useState<GenerationJob[]>([]);
  const [settings, setSettings] = useState<AppSettings | null>(null);

  // Active review state
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisResult | null>(null);

  // Modals state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedTemplateForGen, setSelectedTemplateForGen] = useState<TemplateDetail | null>(null);
  const [completedJob, setCompletedJob] = useState<GenerationJob | null>(null);

  // Delete confirm modal state
  const [deleteConfirmDocId, setDeleteConfirmDocId] = useState<string | null>(null);
  const [deleteConfirmTitle, setDeleteConfirmTitle] = useState('');

  const [isSavingTemplate, setIsSavingTemplate] = useState(false);

  // Initial data load
  const loadInitialData = async () => {
    try {
      const [tpls, gens, sets] = await Promise.all([
        api.listTemplates(),
        api.listGenerations(),
        api.getSettings(),
      ]);
      setTemplates(tpls);
      setRecentGenerations(gens);
      setSettings(sets);
    } catch (e) {
      console.error('Error fetching initial data:', e);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // When analysis completes
  const handleAnalysisComplete = (result: AnalysisResult) => {
    setActiveAnalysis(result);
    setCurrentTab('review');
  };

  // Save template from review
  const handleSaveTemplate = async (name: string, variables: VariableItem[], occurrences: Occurrence[]) => {
    if (!activeAnalysis) return;
    setIsSavingTemplate(true);
    try {
      const saved = await api.saveTemplate(name, activeAnalysis.document_id, variables, occurrences);
      await loadInitialData();
      // Prompt to immediately reuse / generate
      setSelectedTemplateForGen(saved);
      setCurrentTab('library');
    } catch (err: any) {
      alert(`Failed to save template: ${err.message}`);
    } finally {
      setIsSavingTemplate(false);
    }
  };

  // Select template to generate
  const handleSelectTemplate = async (templateId: string) => {
    try {
      const detail = await api.getTemplate(templateId);
      setSelectedTemplateForGen(detail);
    } catch (err: any) {
      alert(`Could not load template details: ${err.message}`);
    }
  };

  // Generation complete
  const handleGenerationComplete = async (job: GenerationJob) => {
    setSelectedTemplateForGen(null);
    setCompletedJob(job);
    const gens = await api.listGenerations();
    setRecentGenerations(gens);
  };

  // Delete template
  const handleDeletePrompt = (sourceDocId: string, templateName: string) => {
    setDeleteConfirmDocId(sourceDocId);
    setDeleteConfirmTitle(templateName);
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirmDocId) return;
    try {
      await api.deleteDocument(deleteConfirmDocId);
      setDeleteConfirmDocId(null);
      await loadInitialData();
      if (activeAnalysis?.document_id === deleteConfirmDocId) {
        setActiveAnalysis(null);
        setCurrentTab('library');
      }
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        onOpenUpload={() => setIsUploadOpen(true)}
        settings={settings}
        hasActiveReview={Boolean(activeAnalysis)}
      />

      <main style={{ flex: 1, paddingBottom: 60 }}>
        {currentTab === 'library' && (
          <LibraryView
            templates={templates}
            recentGenerations={recentGenerations}
            onSelectTemplate={handleSelectTemplate}
            onDeleteTemplate={handleDeletePrompt}
            onOpenUpload={() => setIsUploadOpen(true)}
          />
        )}

        {currentTab === 'review' && activeAnalysis && (
          <ReviewView
            analysis={activeAnalysis}
            onSaveTemplate={handleSaveTemplate}
            isSaving={isSavingTemplate}
          />
        )}

        {currentTab === 'settings' && (
          <SettingsView
            initialSettings={settings}
            onSettingsUpdated={(newSets) => setSettings(newSets)}
          />
        )}
      </main>

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onAnalysisComplete={handleAnalysisComplete}
      />

      {/* Generation Wizard Modal */}
      <GenerationModal
        isOpen={Boolean(selectedTemplateForGen)}
        template={selectedTemplateForGen}
        onClose={() => setSelectedTemplateForGen(null)}
        onGenerationComplete={handleGenerationComplete}
      />

      {/* Results & Verification Modal */}
      <ResultsModal
        isOpen={Boolean(completedJob)}
        job={completedJob}
        onClose={() => setCompletedJob(null)}
        onGenerateAgain={() => {
          const tId = completedJob?.template_id;
          setCompletedJob(null);
          if (tId) handleSelectTemplate(tId);
        }}
      />

      {/* Cascading Deletion Confirm Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteConfirmDocId)}
        title="Confirm Permanent Deletion"
        message={`Are you sure you want to delete template "${deleteConfirmTitle}" and its source document? This action is permanent and cannot be undone.`}
        affectedFiles={[
          'Database record & immutable version history',
          'Associated template variable mappings & occurrences',
          'Physical source file on disk in storage/originals',
          'Temporary working copies & generated artifacts',
        ]}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteConfirmDocId(null)}
      />
    </div>
  );
};

export default App;
