import React, { useState } from 'react';
import { Sparkles, X, AlertCircle, Loader2, ArrowRight } from 'lucide-react';
import type { TemplateDetail, GenerationJob } from '../../types';
import { api } from '../../api/client';

interface GenerationModalProps {
  isOpen: boolean;
  template: TemplateDetail | null;
  onClose: () => void;
  onGenerationComplete: (job: GenerationJob) => void;
}

export const GenerationModal: React.FC<GenerationModalProps> = ({
  isOpen,
  template,
  onClose,
  onGenerationComplete,
}) => {
  if (!isOpen || !template) return null;

  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const v of template.variables) {
      if (v.status === 'approved') {
        initial[v.id] = v.replacement_value || '';
      }
    }
    return initial;
  });

  const [outputFormat, setOutputFormat] = useState<'docx' | 'pdf'>(
    template.source_format === 'pdf' ? 'pdf' : 'docx'
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const approvedVars = template.variables.filter((v) => v.status === 'approved');

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setErrorMessage('');

    try {
      const job = await api.generateDocument(template.id, values, outputFormat);
      onGenerationComplete(job);
    } catch (err: any) {
      setErrorMessage(err.message || 'Generation failed.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: 620, padding: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 20, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
              <Sparkles size={20} color="#a855f7" />
              Generate New Document
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              Template: <strong>{template.name}</strong> (v{template.version})
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        {errorMessage && (
          <div style={{
            background: 'var(--danger-bg)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 8,
            padding: 12,
            fontSize: 13,
            color: '#fca5a5',
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}>
            <AlertCircle size={18} />
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleGenerate}>
          <div style={{ maxHeight: 380, overflowY: 'auto', paddingRight: 6, display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 20 }}>
            {approvedVars.map((v) => (
              <div
                key={v.id}
                style={{
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 10,
                  padding: 12,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {v.label}
                    {v.required && <span style={{ color: '#f87171' }}>*</span>}
                  </label>
                  <span className={`badge badge-${v.type}`}>{v.type}</span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: 10, alignItems: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Original: <span style={{ fontFamily: 'monospace', color: '#94a3b8' }}>{v.original_value}</span>
                  </div>
                  <input
                    type="text"
                    required={v.required}
                    value={values[v.id] || ''}
                    onChange={(e) => setValues({ ...values, [v.id]: e.target.value })}
                    placeholder={`New ${v.label.toLowerCase()}...`}
                    className="input-field"
                    style={{ fontSize: 13, padding: '6px 10px' }}
                  />
                </div>
              </div>
            ))}

            {approvedVars.length === 0 && (
              <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>
                No approved variables in this template.
              </div>
            )}
          </div>

          {/* Format selector */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(0, 0, 0, 0.2)',
            padding: '12px 16px',
            borderRadius: 10,
            border: '1px solid var(--border-subtle)',
            marginBottom: 20,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Target Output Format:</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={() => setOutputFormat('docx')}
                style={{
                  background: outputFormat === 'docx' ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                  border: outputFormat === 'docx' ? '1px solid var(--accent-primary)' : '1px solid transparent',
                  color: outputFormat === 'docx' ? '#fff' : 'var(--text-muted)',
                  borderRadius: 6,
                  padding: '6px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Word (.docx)
              </button>
              <button
                type="button"
                onClick={() => setOutputFormat('pdf')}
                style={{
                  background: outputFormat === 'pdf' ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                  border: outputFormat === 'pdf' ? '1px solid var(--accent-primary)' : '1px solid transparent',
                  color: outputFormat === 'pdf' ? '#fff' : 'var(--text-muted)',
                  borderRadius: 6,
                  padding: '6px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                PDF (.pdf)
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isGenerating}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isGenerating}>
              {isGenerating ? (
                <>
                  <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                  Applying & Validating...
                </>
              ) : (
                <>
                  Generate Output
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
