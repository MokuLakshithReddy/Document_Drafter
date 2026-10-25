import React, { useState, useRef } from 'react';
import { UploadCloud, CheckCircle2, AlertCircle, Loader2, X, File, ShieldCheck } from 'lucide-react';
import { api } from '../../api/client';
import type { AnalysisResult } from '../../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAnalysisComplete: (result: AnalysisResult) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onAnalysisComplete,
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<'idle' | 'uploading' | 'analyzing' | 'done' | 'error'>('idle');
  const [statusMessage, setStatusMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFile = async (file: File) => {
    setSelectedFile(file);
    setUploadState('uploading');
    setStatusMessage('Validating file signature and security constraints...');
    setErrorMessage('');

    try {
      // 1. Upload & validate
      const doc = await api.uploadDocument(file);

      // 2. Start analysis
      setUploadState('analyzing');
      setStatusMessage('Extracting document structure, runs, tables, and detecting variable fields...');
      const analysis = await api.analyzeDocument(doc.id);

      setUploadState('done');
      setStatusMessage('Analysis complete!');
      setTimeout(() => {
        onAnalysisComplete(analysis);
        onClose();
      }, 700);
    } catch (err: any) {
      setUploadState('error');
      let msg = err.message || 'An error occurred during upload or analysis.';
      if (msg === 'Failed to fetch' || msg.includes('NetworkError')) {
        msg = 'Could not connect to backend server at http://127.0.0.1:8000. Please ensure the backend server is running.';
      }
      setErrorMessage(msg);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const onSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: 540, padding: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontSize: 20, fontWeight: 700 }}>Upload Reference Document</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              Supports Microsoft Word (.docx) and text-based PDF documents
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        {uploadState === 'idle' && (
          <div>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.15)'}`,
                background: dragOver ? 'rgba(99, 102, 241, 0.08)' : 'rgba(15, 23, 42, 0.4)',
                borderRadius: 14,
                padding: '40px 20px',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept=".docx,.pdf"
                onChange={onSelectFile}
              />
              <div style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                background: 'rgba(99, 102, 241, 0.15)',
                color: 'var(--accent-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
              }}>
                <UploadCloud size={28} />
              </div>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>
                Click to browse or drag & drop file here
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                DOCX or PDF up to 25MB (Max 100 pages)
              </div>
            </div>

            {/* Security checklist note */}
            <div style={{
              marginTop: 20,
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 10,
              padding: 14,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: '#10b981', marginBottom: 6 }}>
                <ShieldCheck size={16} />
                Local-First Security Protections Active
              </div>
              <ul style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 18, lineHeight: 1.6 }}>
                <li>Binary signature validation (rejects renamed/spoofed files)</li>
                <li>ZIP bomb compression ratio defense</li>
                <li>Macro rejection (.docm / VBA scripts blocked)</li>
                <li>Private local storage (outside web server root)</li>
              </ul>
            </div>
          </div>
        )}

        {(uploadState === 'uploading' || uploadState === 'analyzing') && (
          <div style={{ textAlign: 'center', padding: '30px 20px' }}>
            <Loader2 size={36} className="spin" color="#818cf8" style={{ margin: '0 auto 16px', animation: 'spin 1s linear infinite' }} />
            <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Processing Document</h4>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
              {statusMessage}
            </p>
            {selectedFile && (
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                background: 'rgba(255, 255, 255, 0.05)',
                padding: '6px 14px',
                borderRadius: 20,
                fontSize: 12,
                color: 'var(--text-dim)',
              }}>
                <File size={14} />
                {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
              </div>
            )}
          </div>
        )}

        {uploadState === 'done' && (
          <div style={{ textAlign: 'center', padding: '30px 20px' }}>
            <CheckCircle2 size={40} color="#10b981" style={{ margin: '0 auto 16px' }} />
            <h4 style={{ fontSize: 16, fontWeight: 700, color: '#10b981' }}>Analysis Successful!</h4>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Opening Review Workspace...</p>
          </div>
        )}

        {uploadState === 'error' && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <AlertCircle size={40} color="#ef4444" style={{ margin: '0 auto 16px' }} />
            <h4 style={{ fontSize: 16, fontWeight: 700, color: '#f87171', marginBottom: 8 }}>Upload Rejected</h4>
            <div style={{
              background: 'var(--danger-bg)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 8,
              padding: 12,
              fontSize: 13,
              color: '#fca5a5',
              marginBottom: 20,
              textAlign: 'left',
            }}>
              {errorMessage}
            </div>
            <button className="btn btn-secondary" onClick={() => setUploadState('idle')}>
              Try Again with Another Document
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
