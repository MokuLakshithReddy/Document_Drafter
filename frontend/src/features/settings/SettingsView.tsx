import React, { useState, useEffect } from 'react';
import { Settings, Shield, HardDrive, Key, Save, CheckCircle2, Lock, UserCheck } from 'lucide-react';
import type { AppSettings } from '../../types';
import { api, getApiKey, setApiKey, getSessionId } from '../../api/client';

interface SettingsViewProps {
  initialSettings: AppSettings | null;
  onSettingsUpdated: (settings: AppSettings) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  initialSettings,
  onSettingsUpdated,
}) => {
  const [provider, setProvider] = useState(initialSettings?.ai_provider || 'deterministic');
  const [geminiKey, setGeminiKey] = useState('');
  const [appApiKey, setAppApiKey] = useState(getApiKey());
  const [retentionDays, setRetentionDays] = useState(initialSettings?.file_retention_days || 30);
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (initialSettings) {
      setProvider(initialSettings.ai_provider);
      setRetentionDays(initialSettings.file_retention_days);
    }
  }, [initialSettings]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSavedSuccess(false);

    try {
      setApiKey(appApiKey.trim());
      const updated = await api.updateSettings({
        ai_provider: provider,
        gemini_api_key: geminiKey || undefined,
        file_retention_days: Number(retentionDays),
      });
      onSettingsUpdated(updated);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      alert('Failed to update settings');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '30px auto', padding: '0 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <div style={{
          background: 'rgba(99, 102, 241, 0.15)',
          padding: 10,
          borderRadius: 10,
          color: 'var(--accent-primary)',
        }}>
          <Settings size={22} />
        </div>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em' }}>Application Settings</h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Manage local storage, security parameters, and AI classification providers.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* AI Provider Card */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Shield size={18} color="#10b981" />
            AI & Semantic Extraction Provider
          </h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            Choose how variable candidates are detected. Deterministic mode runs 100% locally on your machine with zero external network calls.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
            <label style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
              padding: 12,
              borderRadius: 8,
              background: provider === 'deterministic' ? 'rgba(99, 102, 241, 0.12)' : 'rgba(0, 0, 0, 0.2)',
              border: provider === 'deterministic' ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}>
              <input
                type="radio"
                name="provider"
                value="deterministic"
                checked={provider === 'deterministic'}
                onChange={() => setProvider('deterministic')}
                style={{ marginTop: 3 }}
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Deterministic Local Engine (Offline / Private)</div>
                <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                  Regex & heuristic pattern extraction for dates, amounts, names, emails, phones, and IDs. Complete privacy.
                </div>
              </div>
            </label>

            <label style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
              padding: 12,
              borderRadius: 8,
              background: provider === 'gemini' ? 'rgba(99, 102, 241, 0.12)' : 'rgba(0, 0, 0, 0.2)',
              border: provider === 'gemini' ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}>
              <input
                type="radio"
                name="provider"
                value="gemini"
                checked={provider === 'gemini'}
                onChange={() => setProvider('gemini')}
                style={{ marginTop: 3 }}
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Google Gemini API (Cloud Semantic Classifier)</div>
                <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                  Provides semantic classification into structured schema. Payload is strictly restricted to text snippets.
                </div>
              </div>
            </label>
          </div>

          {provider === 'gemini' && (
            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <Key size={14} />
                Gemini API Key
              </label>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder={initialSettings?.has_gemini_key ? '••••••••••••••••••••••••• (Key Configured)' : 'Enter your Gemini API key'}
                className="input-field"
              />
            </div>
          )}
        </div>

        {/* Storage & Retention Card */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <HardDrive size={18} color="#818cf8" />
            Storage & Retention Limits
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                Max Upload File Size
              </label>
              <input
                type="text"
                disabled
                value={`${initialSettings?.max_upload_size_mb || 25} MB`}
                className="input-field"
                style={{ opacity: 0.7 }}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                Max Page Count
              </label>
              <input
                type="text"
                disabled
                value={`${initialSettings?.max_page_limit || 100} pages`}
                className="input-field"
                style={{ opacity: 0.7 }}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
              Local Storage Path
            </label>
            <input
              type="text"
              disabled
              value={initialSettings?.storage_dir || './storage'}
              className="input-field"
              style={{ opacity: 0.7, fontFamily: 'monospace', fontSize: 12 }}
            />
          </div>
        </div>

        {/* Authentication & Session Card */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <UserCheck size={18} color="#38bdf8" />
            API Authentication & Session Isolation
          </h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            When deployed to a remote environment with authentication enabled, enter your authorized API key below. Requests are automatically tagged with your client session ID to isolate uploaded documents and templates.
          </p>

          <div style={{ marginBottom: 14 }}>
            <label style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <Key size={14} />
              Client API Key (Optional for Local, Required if API_KEY configured)
            </label>
            <input
              type="password"
              value={appApiKey}
              onChange={(e) => setAppApiKey(e.target.value)}
              placeholder="Enter API Key (sent via X-API-Key)"
              className="input-field"
            />
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>
              Current Client Session ID
            </label>
            <input
              type="text"
              disabled
              value={getSessionId()}
              className="input-field"
              style={{ opacity: 0.7, fontFamily: 'monospace', fontSize: 12 }}
            />
            <span style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
              Isolated to your browser instance. Other sessions cannot access or modify your uploaded files.
            </span>
          </div>
        </div>

        {/* Security Notice */}
        <div style={{
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          borderRadius: 12,
          padding: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          color: '#6ee7b7',
        }}>
          <Lock size={20} />
          <div style={{ fontSize: 12 }}>
            <strong>Localhost Security:</strong> This instance is bound exclusively to <code style={{ color: '#fff' }}>127.0.0.1</code> and rejects non-local connections. Stored documents reside outside the public web root.
          </div>
        </div>

        {/* Submit */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
          {savedSuccess && (
            <span style={{ fontSize: 13, color: '#10b981', display: 'flex', alignItems: 'center', gap: 6 }}>
              <CheckCircle2 size={16} />
              Settings saved!
            </span>
          )}
          <button type="submit" className="btn btn-primary" disabled={isSaving}>
            <Save size={16} />
            {isSaving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
};
