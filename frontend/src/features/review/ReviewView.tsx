import React, { useState } from 'react';
import {
  Split,
  Plus,
  Save,
  AlertTriangle,
  Info,
  MapPin,
  Eye,
  SlidersHorizontal,
  FileCheck2,
} from 'lucide-react';
import type { AnalysisResult, VariableItem, Occurrence, VariableType } from '../../types';

interface ReviewViewProps {
  analysis: AnalysisResult;
  onSaveTemplate: (name: string, variables: VariableItem[], occurrences: Occurrence[]) => Promise<void>;
  isSaving: boolean;
}

export const ReviewView: React.FC<ReviewViewProps> = ({
  analysis,
  onSaveTemplate,
  isSaving,
}) => {
  const [variables, setVariables] = useState<VariableItem[]>(analysis.variables);
  const [occurrences, setOccurrences] = useState<Occurrence[]>(analysis.occurrences);
  const [templateName, setTemplateName] = useState(
    `Template - ${analysis.document_type.replace(/_/g, ' ').toUpperCase()}`
  );
  const [inspectingOccurrencesFor, setInspectingOccurrencesFor] = useState<VariableItem | null>(null);

  // Manual Add Modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newVarLabel, setNewVarLabel] = useState('');
  const [newVarType, setNewVarType] = useState<VariableType>('custom');
  const [newVarOrigValue, setNewVarOrigValue] = useState('');

  // Update label
  const updateLabel = (id: string, label: string) => {
    setVariables((prev) =>
      prev.map((v) => (v.id === id ? { ...v, label } : v))
    );
  };

  // Update replacement value
  const updateReplacement = (id: string, val: string) => {
    setVariables((prev) =>
      prev.map((v) => (v.id === id ? { ...v, replacement_value: val } : v))
    );
  };

  // Split occurrence (AT-08)
  const handleSplitOccurrence = (v: VariableItem, occIdToSplit: string) => {
    if (v.occurrence_ids.length <= 1) return;

    const remainingOccIds = v.occurrence_ids.filter((id) => id !== occIdToSplit);
    const newVarId = `var_split_${Date.now()}`;
    const newVariable: VariableItem = {
      id: newVarId,
      key: `${v.key}_split`,
      label: `${v.label} (Isolated)`,
      type: v.type,
      original_value: v.original_value,
      replacement_value: '',
      occurrence_ids: [occIdToSplit],
      confidence: v.confidence,
      reason: 'Split occurrence separated by user',
      required: false,
      status: 'active',
    };

    // Update occurrences mapping
    setOccurrences((prev) =>
      prev.map((o) => (o.id === occIdToSplit ? { ...o, variable_id: newVarId } : o))
    );

    // Update original variable
    setVariables((prev) => [
      ...prev.map((item) =>
        item.id === v.id ? { ...item, occurrence_ids: remainingOccIds } : item
      ),
      newVariable,
    ]);

    setInspectingOccurrencesFor(null);
  };

  // Manual Add Variable
  const handleAddVariable = () => {
    if (!newVarLabel.trim() || !newVarOrigValue.trim()) return;

    const newId = `var_manual_${Date.now()}`;
    const newOccId = `occ_manual_${Date.now()}`;

    const newOcc: Occurrence = {
      id: newOccId,
      variable_id: newId,
      original_text: newVarOrigValue,
      source_locator: {
        kind: 'paragraph',
        container_id: 'auto',
      },
      status: 'active',
    };

    const newVar: VariableItem = {
      id: newId,
      key: newVarLabel.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
      label: newVarLabel,
      type: newVarType,
      original_value: newVarOrigValue,
      replacement_value: '',
      occurrence_ids: [newOccId],
      confidence: 1.0,
      reason: 'Manually added by user',
      required: false,
      status: 'active',
    };

    setOccurrences((prev) => [...prev, newOcc]);
    setVariables((prev) => [...prev, newVar]);
    setShowAddModal(false);
    setNewVarLabel('');
    setNewVarOrigValue('');
  };

  return (
    <div style={{ maxWidth: 1300, margin: '24px auto', padding: '0 20px' }}>
      {/* Top Header & Save Banner */}
      <div className="glass-panel" style={{ padding: '20px 24px', marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 700, background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', padding: '3px 8px', borderRadius: 6 }}>
              {analysis.document_type.toUpperCase()}
            </span>
            <input
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              className="input-field"
              style={{ fontWeight: 700, fontSize: 18, width: 380, padding: '4px 10px' }}
              placeholder="Template Name..."
            />
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Detected {variables.length} variables across {occurrences.length} structural locations. Enter optional new values, or leave blank to keep original text.
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-secondary" onClick={() => setShowAddModal(true)}>
            <Plus size={16} />
            Add Variable
          </button>
          <button
            className="btn btn-primary"
            disabled={isSaving}
            onClick={() => onSaveTemplate(templateName, variables, occurrences)}
          >
            <Save size={16} />
            {isSaving ? 'Saving Template...' : 'Save As Reusable Template'}
          </button>
        </div>
      </div>

      {/* Scanned PDF warning notice if applicable (AT-11) */}
      {analysis.is_scanned && (
        <div style={{
          background: 'var(--warning-bg)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          borderRadius: 12,
          padding: 16,
          marginBottom: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          color: '#fcd34d',
        }}>
          <AlertTriangle size={24} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 14 }}>Scanned Document Detected (OCR Limitation)</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {analysis.warning || 'This document contains non-selectable image layers. Automatic variable extraction requires selectable text.'}
            </div>
          </div>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 24, alignItems: 'start' }}>
        {/* Left Column: Document Preview */}
        <div className="glass-panel" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 10 }}>
            <h4 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Eye size={16} color="#818cf8" />
              Document Text Preview
            </h4>
            <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
              {analysis.total_paragraphs} paragraphs · {analysis.total_tables} tables
            </span>
          </div>

          <div style={{
            background: 'rgba(0, 0, 0, 0.4)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 10,
            padding: 16,
            maxHeight: 520,
            overflowY: 'auto',
            fontFamily: 'monospace',
            fontSize: 13,
            lineHeight: 1.7,
            whiteSpace: 'pre-wrap',
            color: '#e2e8f0',
          }}>
            {analysis.extracted_text_preview || 'No text extracted from document.'}
          </div>

          <div style={{ marginTop: 14, fontSize: 12, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Info size={14} />
            Review detected variables on the right. Any field left blank or omitted will keep its original text in the document.
          </div>
        </div>

        {/* Right Column: Variable Candidates */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h4 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
              <SlidersHorizontal size={16} color="#a855f7" />
              Detected Variables ({variables.length})
            </h4>
            <div style={{ fontSize: 12, color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
              <FileCheck2 size={14} />
              Blank fields remain unchanged
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 580, overflowY: 'auto', paddingRight: 4 }}>
            {variables.map((v) => {
              const hasCustomValue = Boolean(v.replacement_value && v.replacement_value.trim());

              return (
                <div
                  key={v.id}
                  className="glass-panel"
                  style={{
                    padding: 14,
                    border: hasCustomValue
                      ? '1px solid rgba(99, 102, 241, 0.45)'
                      : '1px solid rgba(255, 255, 255, 0.08)',
                    background: hasCustomValue
                      ? 'rgba(30, 41, 59, 0.75)'
                      : 'rgba(15, 23, 42, 0.45)',
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                      <span className={`badge badge-${v.type}`}>{v.type}</span>
                      <input
                        type="text"
                        value={v.label}
                        onChange={(e) => updateLabel(v.id, e.target.value)}
                        className="input-field"
                        style={{
                          fontWeight: 700,
                          fontSize: 13,
                          padding: '2px 8px',
                          background: 'transparent',
                          border: '1px solid transparent',
                          borderRadius: 4,
                          color: '#fff',
                          width: '70%',
                        }}
                        onFocus={(e) => (e.target.style.borderColor = 'var(--accent-primary)')}
                        onBlur={(e) => (e.target.style.borderColor = 'transparent')}
                        title="Click to edit field label"
                      />
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {/* Occurrence inspection button */}
                      <button
                        onClick={() => setInspectingOccurrencesFor(v)}
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: 11 }}
                        title="Inspect occurrences"
                      >
                        <MapPin size={12} />
                        {v.occurrence_ids.length} occ
                      </button>
                    </div>
                  </div>

                  {/* Values grid (original vs replacement) */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 4 }}>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>Original in Source:</div>
                      <div style={{
                        background: 'rgba(0,0,0,0.3)',
                        padding: '8px 10px',
                        borderRadius: 6,
                        fontSize: 12,
                        fontFamily: 'monospace',
                        color: '#94a3b8',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>
                        {v.original_value}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
                        New Replacement Value:
                      </div>
                      <input
                        type="text"
                        className="input-field"
                        placeholder="Leave blank to keep original"
                        value={v.replacement_value || ''}
                        onChange={(e) => updateReplacement(v.id, e.target.value)}
                        style={{
                          fontSize: 12,
                          padding: '8px 10px',
                          borderColor: hasCustomValue ? 'var(--accent-primary)' : undefined,
                        }}
                      />
                    </div>
                  </div>

                  <div style={{ fontSize: 11, color: hasCustomValue ? '#818cf8' : 'var(--text-dim)', marginTop: 4 }}>
                    {hasCustomValue
                      ? `Will replace with: "${v.replacement_value}"`
                      : 'Will leave original document content unchanged'}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Inspect Occurrences / Split Modal (AT-08) */}
      {inspectingOccurrencesFor && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: 600 }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
              <MapPin size={18} color="#818cf8" />
              Occurrences for: {inspectingOccurrencesFor.label}
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
              Original text: <code style={{ color: '#818cf8' }}>{inspectingOccurrencesFor.original_value}</code>
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 300, overflowY: 'auto', marginBottom: 20 }}>
              {inspectingOccurrencesFor.occurrence_ids.map((occId, idx) => {
                const occ = occurrences.find((o) => o.id === occId);
                return (
                  <div
                    key={occId}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 8,
                      padding: 12,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600 }}>
                        Occurrence #{idx + 1} ({occId})
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                        Location: {occ?.source_locator.container_id}
                        {occ?.source_locator.page !== undefined ? ` · Page ${occ.source_locator.page + 1}` : ''}
                      </div>
                    </div>

                    {inspectingOccurrencesFor.occurrence_ids.length > 1 && (
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: 11, padding: '4px 8px' }}
                        onClick={() => handleSplitOccurrence(inspectingOccurrencesFor, occId)}
                        title="Isolate this occurrence into an independent variable"
                      >
                        <Split size={12} />
                        Isolate Occurrence
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setInspectingOccurrencesFor(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Add Variable Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: 480 }}>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>Add Variable</h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Variable Label
                </label>
                <input
                  type="text"
                  placeholder="e.g. Employee Name, Start Date"
                  value={newVarLabel}
                  onChange={(e) => setNewVarLabel(e.target.value)}
                  className="input-field"
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Original Text Exactly in Document
                </label>
                <input
                  type="text"
                  placeholder="e.g. Rahul Sharma"
                  value={newVarOrigValue}
                  onChange={(e) => setNewVarOrigValue(e.target.value)}
                  className="input-field"
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Variable Type
                </label>
                <select
                  value={newVarType}
                  onChange={(e) => setNewVarType(e.target.value as VariableType)}
                  className="input-field"
                >
                  <option value="custom">Custom</option>
                  <option value="person_name">Person Name</option>
                  <option value="organization">Organization</option>
                  <option value="date">Date</option>
                  <option value="address">Address</option>
                  <option value="money">Money</option>
                  <option value="email">Email</option>
                  <option value="phone">Phone</option>
                  <option value="role">Role / Title</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                <button className="btn btn-secondary" onClick={() => setShowAddModal(false)}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={handleAddVariable}>
                  Add Variable
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
