import React, { useState } from 'react';
import SettingsModal from './SettingsModal';
import CreateAgentModal from './CreateAgentModal';
import { createAgent } from '../api';

const Sidebar = ({ agents, currentAgent, onSelectAgent, agentDetails }) => {
  const [hoveredAgent, setHoveredAgent] = useState(null);
  const [managingSettingsFor, setManagingSettingsFor] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  return (
    <div style={{
      width: '260px',
      height: '100%',
      backgroundColor: 'var(--bg-sidebar)',
      borderRight: '1px solid var(--glass-border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '20px 0 0 0'
    }}>
      <div style={{ padding: '0 20px', marginBottom: '20px' }}>
        <h2 style={{ 
          color: 'var(--accent-primary)',
          fontSize: '1.2rem',
          fontWeight: '700',
          letterSpacing: '1px',
          textTransform: 'uppercase',
          marginBottom: '5px'
        }}>
          Control Panel
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Select Agent Session
        </p>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {agents.length === 0 ? (
          <div style={{ padding: '0 20px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            No agents found.
          </div>
        ) : (
          agents.map(agent => (
            <div
              key={agent}
              onClick={() => onSelectAgent(agent)}
              style={{
                padding: '12px 20px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                transition: 'all 0.2s',
                backgroundColor: currentAgent === agent ? 'var(--bg-surface-hover)' : 'transparent',
                borderLeft: currentAgent === agent ? '4px solid var(--accent-primary)' : '4px solid transparent',
                color: currentAgent === agent ? 'var(--text-main)' : 'var(--text-muted)',
                fontWeight: currentAgent === agent ? '600' : '400',
                height: '46px',
                boxSizing: 'border-box'
              }}
              onMouseEnter={(e) => {
                setHoveredAgent(agent);
                if (currentAgent !== agent) {
                  e.currentTarget.style.backgroundColor = 'var(--bg-surface)';
                  e.currentTarget.style.color = 'var(--text-main)';
                }
              }}
              onMouseLeave={(e) => {
                setHoveredAgent(null);
                if (currentAgent !== agent) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = 'var(--text-muted)';
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: currentAgent === agent ? 'var(--accent-success)' : 'var(--text-muted)',
                  marginRight: '12px',
                  boxShadow: currentAgent === agent ? '0 0 8px var(--accent-success)' : 'none'
                }}></div>
                {agentDetails && agentDetails[agent]?.AI_NAME ? agentDetails[agent].AI_NAME : agent}
              </div>
              
              {hoveredAgent === agent && (
                <div 
                  onClick={(e) => {
                    e.stopPropagation();
                    setManagingSettingsFor(agent);
                  }}
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '4px',
                    color: 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s',
                    zIndex: 10,
                    fontSize: '14px',
                    lineHeight: '1',
                    boxSizing: 'border-box',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--accent-primary)';
                    e.currentTarget.style.backgroundColor = 'var(--bg-main)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--text-muted)';
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                  title="Settings"
                >
                  ⚙️
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div style={{ 
        height: '94px', 
        padding: '0 20px', 
        borderTop: '1px solid var(--glass-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <button
          onClick={() => setShowCreateModal(true)}
          style={{
            width: '100%',
            height: '46px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--glass-border)',
            borderRadius: '6px',
            color: 'var(--text-main)',
            cursor: 'pointer',
            fontWeight: '600',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)';
            e.currentTarget.style.borderColor = 'var(--accent-primary)';
            e.currentTarget.style.color = 'var(--accent-primary)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--bg-surface)';
            e.currentTarget.style.borderColor = 'var(--glass-border)';
            e.currentTarget.style.color = 'var(--text-main)';
          }}
        >
          + Create Agent
        </button>
      </div>

      {managingSettingsFor && (
        <SettingsModal 
          agentName={managingSettingsFor} 
          initialDisplayName={agentDetails && agentDetails[managingSettingsFor] ? agentDetails[managingSettingsFor].AI_NAME : ''}
          onClose={() => setManagingSettingsFor(null)} 
          onSettingsUpdated={(agent, settings) => {
            alert("Settings updated! Please refresh the page to see the changes.");
          }}
        />
      )}

      {showCreateModal && (
        <CreateAgentModal 
          onClose={() => setShowCreateModal(false)}
          onCreate={async (name, displayName) => {
            await createAgent(name, displayName);
            alert("Agent created! Please manually refresh the page to see it in the list.");
            setShowCreateModal(false);
          }}
        />
      )}
    </div>
  );
};

export default Sidebar;
