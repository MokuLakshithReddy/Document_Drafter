import React from 'react';
import { AlertTriangle, Trash2, X } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  affectedFiles?: string[];
  confirmText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  message,
  affectedFiles = [],
  confirmText = 'Delete Permanently',
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: 480, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#f87171' }}>
            <div style={{
              background: 'var(--danger-bg)',
              padding: 8,
              borderRadius: 8,
              display: 'flex',
            }}>
              <AlertTriangle size={20} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-main)' }}>{title}</h3>
          </div>
          <button 
            onClick={onCancel}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 16, lineHeight: 1.6 }}>
          {message}
        </p>

        {affectedFiles.length > 0 && (
          <div style={{
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: 8,
            padding: 12,
            border: '1px solid rgba(239, 68, 68, 0.2)',
            marginBottom: 20,
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#f87171', marginBottom: 6 }}>
              Files that will be permanently erased:
            </div>
            <ul style={{ fontSize: 12, color: 'var(--text-muted)', paddingLeft: 18 }}>
              {affectedFiles.map((f, i) => (
                <li key={i} style={{ fontFamily: 'monospace' }}>{f}</li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm}>
            <Trash2 size={16} />
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
};
