import React from 'react';
import { CheckCircle2, Download, ShieldCheck, AlertTriangle, X, RefreshCw } from 'lucide-react';
import type { GenerationJob } from '../../types';

interface ResultsModalProps {
  isOpen: boolean;
  job: GenerationJob | null;
  onClose: () => void;
  onGenerateAgain: () => void;
}

export const ResultsModal: React.FC<ResultsModalProps> = ({
  isOpen,
  job,
  onClose,
  onGenerateAgain,
}) => {
  if (!isOpen || !job) return null;

  const report = job.validation_report;
  const isPassed = job.status === 'completed' && report?.status !== 'failed';
  const downloadUrl = job.download_url ? `http://127.0.0.1:8000${job.download_url}` : null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: 560, padding: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              background: isPassed ? 'var(--success-bg)' : 'var(--danger-bg)',
              color: isPassed ? '#10b981' : '#f87171',
              padding: 10,
              borderRadius: 12,
              display: 'flex',
            }}>
              {isPassed ? <CheckCircle2 size={24} /> : <AlertTriangle size={24} />}
            </div>
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700 }}>
                {isPassed ? 'Document Generation Complete' : 'Generation Needs Review'}
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Job ID: <span style={{ fontFamily: 'monospace' }}>{job.id.slice(0, 12)}...</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Automated Validation Report Card (Section 11, FR-10) */}
        {report && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 12,
            padding: 16,
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={16} color="#10b981" />
                Automated Integrity Report
              </span>
              <span style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '2px 8px',
                borderRadius: 4,
                background: report.status === 'passed' ? 'var(--success-bg)' : 'var(--warning-bg)',
                color: report.status === 'passed' ? '#34d399' : '#fbbf24',
              }}>
                {report.status}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 10 }}>
              <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: 10, borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>Intended Replacements:</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>
                  {report.verified_replacements_count} / {report.intended_replacements_count} Verified
                </div>
              </div>

              <div style={{ background: 'rgba(0, 0, 0, 0.25)', padding: 10, borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>Protected Text Check:</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: report.protected_content_verified ? '#10b981' : '#f87171' }}>
                  {report.protected_content_verified ? '100% Intact' : 'Unauthorized Alteration'}
                </div>
              </div>
            </div>

            {report.issues && report.issues.length > 0 && (
              <div style={{ marginTop: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#f59e0b', marginBottom: 4 }}>
                  Reported Warnings:
                </div>
                <ul style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 16 }}>
                  {report.issues.map((iss, i) => (
                    <li key={i}>{iss.message}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <button className="btn btn-secondary" onClick={onGenerateAgain}>
            <RefreshCw size={15} />
            Generate Another Document
          </button>

          {downloadUrl && (
            <a
              href={downloadUrl}
              download
              className="btn btn-primary"
              style={{ textDecoration: 'none' }}
            >
              <Download size={16} />
              Download Generated File
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
