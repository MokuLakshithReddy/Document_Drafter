import React, { useState } from 'react';
import {
  Check,
  X,
  Split,
  Plus,
  Save,
  AlertTriangle,
  Info,
  MapPin,
  Eye,
  SlidersHorizontal,
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

  // Set explicit status: approved, excluded, or pending
  const setStatus = (id: string, status: 'approved' | 'excluded' | 'pending') => {
    setVariables((prev) =>
      prev.map((v) => (v.id === id ? { ...v, status } : v))
    );
  };

  const approveAll = () => {
    setVariables((prev) => prev.map((v) => ({ ...v, status: 'approved' })));
  };

  const excludeAll = () => {
    setVariables((prev) => prev.map((v) => ({ ...v, status: 'excluded' })));
  };

  // Update field value
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
      status: 'approved',
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
      status: 'approved',
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
            Detected {variables.length} variable candidates across {occurrences.length} structural locations.
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
              {analysis.warning || 'This document contains non-selectable image layers. In accordance with MVP specification, OCR is not supported; automatic variable extraction requires selectable text.'}
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

          {/* Quick instructions */}
          <div style={{ marginTop: 14, fontSize: 12, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Info size={14} />
            Review candidates on the right. Approved variables will be replaceable in your generated documents.
          </div>
        </div>

        {/* Right Column: Variable Candidates */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h4 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
              <SlidersHorizontal size={16} color="#a855f7" />
              Variable Candidates ({variables.length})
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                onClick={approveAll}
                className="btn btn-secondary"
                style={{ padding: '3px 8px', fontSize: 11, color: '#34d399' }}
              >
                Approve All
              </button>
              <button
                onClick={excludeAll}
                className="btn btn-secondary"
                style={{ padding: '3px 8px', fontSize: 11, color: '#f87171' }}
              >
                Exclude All
              </button>
              <div style={{ fontSize: 12, color: 'var(--text-dim)', marginLeft: 4 }}>
                {variables.filter((v) => v.status === 'approved').length} approved
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 580, overflowY: 'auto', paddingRight: 4 }}>
            {variables.map((v) => {
              const isApproved = v.status === 'approved';
              const isPending = v.status === 'pending';
              const isExcluded = v.status === 'excluded';

              return (
                <div
                  key={v.id}
                  className="glass-panel"
                  style={{
                    padding: 14,
                    border: isApproved
                      ? '1px solid rgba(16, 185, 129, 0.4)'
                      : isPending
                      ? '1px solid rgba(245, 158, 11, 0.4)'
                      : '1px solid rgba(255, 255, 255, 0.05)',
                    background: isApproved
                      ? 'rgba(6, 78, 59, 0.25)'
                      : isPending
                      ? 'rgba(120, 53, 15, 0.2)'
                      : 'rgba(15, 23, 42, 0.4)',
                    opacity: isExcluded ? 0.6 : 1,
                    transition: 'all 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className={`badge badge-${v.type}`}>{v.type}</span>
                      <strong style={{ fontSize: 14, color: isApproved ? '#fff' : isPending ? '#fcd34d' : 'var(--text-muted)' }}>
                        {v.label}
                      </strong>
                      {isPending && (
                        <span style={{ fontSize: 10, background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', padding: '2px 6px', borderRadius: 4, fontWeight: 700 }}>
                          PENDING
                        </span>
                      )}
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

                      {/* Action buttons */}
                      {isPending ? (
                        <>
                          <button
                            onClick={() => setStatus(v.id, 'approved')}
                            style={{
                              background: 'rgba(16, 185, 129, 0.25)',
                              color: '#34d399',
                              border: '1px solid rgba(16, 185, 129, 0.5)',
                              borderRadius: 6,
                              padding: '4px 8px',
                              fontSize: 11,
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <Check size={12} /> Approve
                          </button>
                          <button
                            onClick={() => setStatus(v.id, 'excluded')}
                            style={{
                              background: 'rgba(239, 68, 68, 0.15)',
                              color: '#f87171',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                              borderRadius: 6,
                              padding: '4px 8px',
                              fontSize: 11,
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            Exclude
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => setStatus(v.id, isApproved ? 'excluded' : 'approved')}
                          style={{
                            background: isApproved ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                            color: isApproved ? '#34d399' : '#f87171',
                            border: `1px solid ${isApproved ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
                            borderRadius: 6,
                            padding: '4px 8px',
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          {isApproved ? <Check size={12} /> : <X size={12} />}
                          {isApproved ? 'Approved' : 'Excluded'}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Values grid (original vs replacement) */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 8 }}>
                    <div>
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2 }}>Original in Source:</div>
                      <div style={{
                        background: 'rgba(0,0,0,0.3)',
                        padding: '6px 10px',
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
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2 }}>Default Replacement:</div>
                      <input
                        type="text"
                        value={v.replacement_value || ''}
                        onChange={(e) => updateReplacement(v.id, e.target.value)}
                        placeholder="(Blank by default)"
                        className="input-field"
                        style={{ padding: '5px 8px', fontSize: 12 }}
                      />
                    </div>
                  </div>

                  {/* Reason & Hint */}
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>{v.reason || 'Detected pattern'}</span>
                    <span>Confidence: {(v.confidence ? v.confidence * 100 : 90).toFixed(0)}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Occurrence Inspector & Split Modal (AT-08) */}
      {inspectingOccurrencesFor && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: 500, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <h4 style={{ fontSize: 16, fontWeight: 700 }}>Inspect Occurrences</h4>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Variable: <strong>{inspectingOccurrencesFor.label}</strong> ("{inspectingOccurrencesFor.original_value}")
                </div>
              </div>
              <button
                onClick={() => setInspectingOccurrencesFor(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 14 }}>
              This variable appears in {inspectingOccurrencesFor.occurrence_ids.length} locations. If an occurrence refers to a different context or entity, you can split it into an independent variable.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
              {inspectingOccurrencesFor.occurrence_ids.map((occId, idx) => {
                const occ = occurrences.find((o) => o.id === occId);
                return (
                  <div
                    key={occId}
                    style={{
                      background: 'rgba(0, 0, 0, 0.3)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 8,
                      padding: 10,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
                        Occurrence #{idx + 1} ({occId})
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'monospace' }}>
                        Location: {occ?.source_locator.container_id || 'paragraph'}
                      </div>
                    </div>

                    {inspectingOccurrencesFor.occurrence_ids.length > 1 && (
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: 11 }}
                        onClick={() => handleSplitOccurrence(inspectingOccurrencesFor, occId)}
                      >
                        <Split size={12} />
                        Split Into Separate Variable
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
          <div className="modal-content" style={{ maxWidth: 440, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h4 style={{ fontSize: 16, fontWeight: 700 }}>Add Custom Variable</h4>
              <button
                onClick={() => setShowAddModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  Field Label
                </label>
                <input
                  type="text"
                  placeholder="e.g. Project Code"
                  value={newVarLabel}
                  onChange={(e) => setNewVarLabel(e.target.value)}
                  className="input-field"
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  Entity Type
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
                  <option value="money">Money / Amount</option>
                  <option value="role">Role / Title</option>
                  <option value="email">Email</option>
                  <option value="phone">Phone Number</option>
                  <option value="identifier">Identifier / Code</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                  Original Text in Document to Replace
                </label>
                <input
                  type="text"
                  placeholder="e.g. PRJ-2026"
                  value={newVarOrigValue}
                  onChange={(e) => setNewVarOrigValue(e.target.value)}
                  className="input-field"
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button className="btn btn-secondary" onClick={() => setShowAddModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleAddVariable}>
                <Plus size={14} />
                Add Variable
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
