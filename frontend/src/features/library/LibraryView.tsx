import React from 'react';
import {
  FolderKanban,
  FileText,
  Play,
  Trash2,
  Clock,
  Download,
  Plus,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import type { TemplateSummary, GenerationJob } from '../../types';

interface LibraryViewProps {
  templates: TemplateSummary[];
  recentGenerations: GenerationJob[];
  onSelectTemplate: (templateId: string) => void;
  onDeleteTemplate: (sourceDocId: string, templateName: string) => void;
  onOpenUpload: () => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({
  templates,
  recentGenerations,
  onSelectTemplate,
  onDeleteTemplate,
  onOpenUpload,
}) => {
  return (
    <div style={{ maxWidth: 1200, margin: '30px auto', padding: '0 20px' }}>
      {/* Top Banner */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 28,
      }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 4 }}>
            Template Library
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>
            Reusable reviewed templates. Generate new documents with verified variables anytime.
          </p>
        </div>

        <button className="btn btn-primary" onClick={onOpenUpload}>
          <Plus size={16} />
          New Reference Document
        </button>
      </div>

      {/* Templates Grid */}
      {templates.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '60px 20px', marginBottom: 40 }}>
          <div style={{
            width: 60,
            height: 60,
            borderRadius: '50%',
            background: 'rgba(99, 102, 241, 0.1)',
            color: 'var(--accent-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
          }}>
            <FolderKanban size={30} />
          </div>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>No templates saved yet</h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 420, margin: '0 auto 20px' }}>
            Upload an existing DOCX or PDF reference document, review detected variables, and save it as a reusable template.
          </p>
          <button className="btn btn-primary" onClick={onOpenUpload}>
            <Plus size={16} />
            Upload Your First Document
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: 20,
          marginBottom: 44,
        }}>
          {templates.map((tpl) => (
            <div key={tpl.id} className="glass-panel-interactive" style={{ padding: 20, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <span className={`badge badge-${tpl.source_format === 'pdf' ? 'role' : 'person'}`}>
                    {tpl.source_format.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={12} />
                    {new Date(tpl.created_at).toLocaleDateString()}
                  </span>
                </div>

                <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 6, color: '#fff' }}>
                  {tpl.name}
                </h4>

                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText size={14} color="#94a3b8" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {tpl.source_filename}
                  </span>
                  <span style={{ color: 'var(--text-dim)' }}>· v{tpl.version}</span>
                </div>

                <div style={{
                  background: 'rgba(0, 0, 0, 0.25)',
                  padding: '8px 12px',
                  borderRadius: 8,
                  fontSize: 12,
                  color: 'var(--text-muted)',
                  marginBottom: 18,
                }}>
                  Configured Variables: <strong style={{ color: '#e2e8f0' }}>{tpl.variable_count}</strong>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, borderTop: '1px solid var(--border-subtle)', paddingTop: 14 }}>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '8px 14px', fontSize: 13 }}
                  onClick={() => onSelectTemplate(tpl.id)}
                >
                  <Play size={14} />
                  Reuse & Generate
                </button>
                <button
                  className="btn btn-danger"
                  style={{ padding: '8px 10px' }}
                  onClick={() => onDeleteTemplate(tpl.source_document_id, tpl.name)}
                  title="Delete Template & Documents"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Recent Generation History (FR-14) */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Clock size={18} color="#818cf8" />
          <h3 style={{ fontSize: 18, fontWeight: 700 }}>Recent Generations</h3>
        </div>

        {recentGenerations.length === 0 ? (
          <div className="glass-panel" style={{ padding: 24, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
            No generation jobs recorded yet.
          </div>
        ) : (
          <div className="glass-panel" style={{ overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: 12 }}>
                  <th style={{ padding: '12px 16px' }}>Job ID</th>
                  <th style={{ padding: '12px 16px' }}>Date</th>
                  <th style={{ padding: '12px 16px' }}>Validation Status</th>
                  <th style={{ padding: '12px 16px' }}>Integrity Check</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Download</th>
                </tr>
              </thead>
              <tbody>
                {recentGenerations.map((job) => {
                  const passed = job.status === 'completed';
                  return (
                    <tr key={job.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                      <td style={{ padding: '12px 16px', fontFamily: 'monospace', color: '#94a3b8' }}>
                        {job.id.slice(0, 8)}...
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>
                        {new Date(job.created_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          fontSize: 11,
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          color: passed ? '#34d399' : '#f87171',
                        }}>
                          {passed ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                          {job.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>
                        {job.validation_report ? (
                          <span>
                            {job.validation_report.verified_replacements_count}/{job.validation_report.intended_replacements_count} verified
                          </span>
                        ) : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        {job.download_url ? (
                          <a
                            href={`http://127.0.0.1:8000${job.download_url}`}
                            download
                            className="btn btn-secondary"
                            style={{ padding: '4px 10px', fontSize: 12, textDecoration: 'none' }}
                          >
                            <Download size={13} />
                            Download
                          </a>
                        ) : (
                          <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>Unavailable</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
