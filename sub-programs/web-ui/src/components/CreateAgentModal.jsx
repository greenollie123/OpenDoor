import React, { useState } from 'react';

const CreateAgentModal = ({ onClose, onCreate }) => {
  const [agentName, setAgentName] = useState('');
  const [agentDisplayName, setAgentDisplayName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!agentName.trim()) return;
    
    setLoading(true);
    await onCreate(agentName.trim(), agentDisplayName.trim());
    setLoading(false);
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.6)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: 'var(--bg-main)',
        border: '1px solid var(--glass-border)',
        borderRadius: '12px',
        width: '400px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid var(--glass-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>
            Create New Agent
          </h2>
          <button 
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              fontSize: '1.5rem',
              cursor: 'pointer'
            }}
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ color: 'var(--text-main)', fontSize: '0.9rem', fontWeight: '500' }}>
                Agent File Name *
              </label>
              <input 
                type="text" 
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="e.g. my_agent_1"
                required
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--glass-border)',
                  backgroundColor: 'var(--bg-surface)',
                  color: 'var(--text-main)',
                  outline: 'none',
                  fontSize: '0.95rem'
                }}
              />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                Used for folder naming (no spaces recommended).
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ color: 'var(--text-main)', fontSize: '0.9rem', fontWeight: '500' }}>
                Agent Display Name
              </label>
              <input 
                type="text" 
                value={agentDisplayName}
                onChange={(e) => setAgentDisplayName(e.target.value)}
                placeholder="e.g. My Awesome Agent"
                style={{
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--glass-border)',
                  backgroundColor: 'var(--bg-surface)',
                  color: 'var(--text-main)',
                  outline: 'none',
                  fontSize: '0.95rem'
                }}
              />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                Optional. How the agent appears in the UI.
              </span>
            </div>

          </div>

          {/* Footer */}
          <div style={{
            padding: '16px 20px',
            borderTop: '1px solid var(--glass-border)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '12px',
            backgroundColor: 'var(--bg-sidebar)',
            borderBottomLeftRadius: '12px',
            borderBottomRightRadius: '12px'
          }}>
            <button 
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                border: '1px solid var(--glass-border)',
                color: 'var(--text-main)',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button 
              type="submit"
              disabled={loading || !agentName.trim()}
              style={{
                padding: '8px 16px',
                backgroundColor: 'var(--accent-primary)',
                border: 'none',
                color: '#fff',
                borderRadius: '6px',
                cursor: (loading || !agentName.trim()) ? 'not-allowed' : 'pointer',
                fontWeight: '500',
                opacity: (loading || !agentName.trim()) ? 0.7 : 1
              }}
            >
              {loading ? 'Creating...' : 'Create Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateAgentModal;
