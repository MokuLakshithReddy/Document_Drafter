import React from 'react';
import { FileText, Cpu, Shield, Settings, Plus, FolderKanban } from 'lucide-react';
import type { AppSettings } from '../types';

interface NavbarProps {
  currentTab: 'library' | 'review' | 'settings';
  setCurrentTab: (tab: 'library' | 'review' | 'settings') => void;
  onOpenUpload: () => void;
  settings: AppSettings | null;
  hasActiveReview: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  setCurrentTab,
  onOpenUpload,
  settings,
  hasActiveReview,
}) => {
  return (
    <header style={{
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(11, 15, 25, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '12px 24px',
    }}>
      <div style={{
        maxWidth: 1300,
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        {/* Brand */}
        <div 
          onClick={() => setCurrentTab('library')}
          style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}
        >
          <div style={{
            background: 'var(--accent-gradient)',
            padding: 8,
            borderRadius: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)',
          }}>
            <FileText size={20} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: 8 }}>
              DocReuse AI
              <span style={{
                fontSize: 10,
                background: 'rgba(255, 255, 255, 0.1)',
                padding: '2px 6px',
                borderRadius: 4,
                fontWeight: 600,
                color: 'var(--text-muted)'
              }}>LOCAL MVP</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              Deterministic & AI-Assisted Document Reuse
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => setCurrentTab('library')}
            style={{
              background: currentTab === 'library' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
              color: currentTab === 'library' ? '#fff' : 'var(--text-muted)',
              border: 'none',
              padding: '8px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              transition: 'all 0.2s',
            }}
          >
            <FolderKanban size={16} />
            Template Library
          </button>

          {hasActiveReview && (
            <button
              onClick={() => setCurrentTab('review')}
              style={{
                background: currentTab === 'review' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                color: currentTab === 'review' ? '#818cf8' : 'var(--text-muted)',
                border: currentTab === 'review' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                padding: '8px 16px',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                transition: 'all 0.2s',
              }}
            >
              <Cpu size={16} />
              Review Workspace
            </button>
          )}

          <button
            onClick={() => setCurrentTab('settings')}
            style={{
              background: currentTab === 'settings' ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
              color: currentTab === 'settings' ? '#fff' : 'var(--text-muted)',
              border: 'none',
              padding: '8px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              transition: 'all 0.2s',
            }}
          >
            <Settings size={16} />
            Settings
          </button>
        </nav>

        {/* Right Actions & Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* AI Mode Indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid var(--border-subtle)',
            padding: '5px 10px',
            borderRadius: 20,
            fontSize: 11,
            color: 'var(--text-muted)',
          }}>
            <Shield size={13} color={settings?.ai_provider === 'deterministic' ? '#10b981' : '#6366f1'} />
            <span>AI: <strong style={{ color: '#fff' }}>{settings?.ai_provider || 'Deterministic (Offline)'}</strong></span>
          </div>

          {/* Upload Button */}
          <button className="btn btn-primary" onClick={onOpenUpload}>
            <Plus size={16} />
            Upload Document
          </button>
        </div>
      </div>
    </header>
  );
};
