import React, { useState, useEffect } from 'react';
import { fetchAgentTools, updateAgentTools, updateAgentSettings, fetchAgentSkills, updateAgentSkills } from '../api';

const SettingsModal = ({ agentName, initialDisplayName, onClose, onSettingsUpdated }) => {
  const [activeTab, setActiveTab] = useState('General');
  
  // Tools state
  const [allTools, setAllTools] = useState([]);
  const [disabledTools, setDisabledTools] = useState([]);
  const [needsRestart, setNeedsRestart] = useState([]);
  const [loadingTools, setLoadingTools] = useState(true);

  // Skills state
  const [allSkills, setAllSkills] = useState([]);
  const [disabledSkills, setDisabledSkills] = useState([]);
  const [loadingSkills, setLoadingSkills] = useState(true);
  
  // General state
  const [displayName, setDisplayName] = useState(initialDisplayName || agentName);
  
  // Common state
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (activeTab === 'Tools' && allTools.length === 0) {
      loadTools();
    }
    if (activeTab === 'Skills' && allSkills.length === 0) {
      loadSkills();
    }
  }, [activeTab]);

  const loadTools = async () => {
    setLoadingTools(true);
    const data = await fetchAgentTools(agentName);
    setAllTools(data.all_tools || []);
    setDisabledTools(data.disabled_tools || []);
    setNeedsRestart(data.needs_restart || []);
    setLoadingTools(false);
  };

  const loadSkills = async () => {
    setLoadingSkills(true);
    const data = await fetchAgentSkills(agentName);
    setAllSkills(data.all_skills || []);
    setDisabledSkills(data.disabled_skills || []);
    setLoadingSkills(false);
  };

  const handleToggleTool = (toolName) => {
    setDisabledTools(prev => {
      if (prev.includes(toolName)) return prev.filter(t => t !== toolName);
      return [...prev, toolName];
    });
  };

  const handleToggleSkill = (skillName) => {
    setDisabledSkills(prev => {
      if (prev.includes(skillName)) return prev.filter(s => s !== skillName);
      return [...prev, skillName];
    });
  };

  const handleSave = async () => {
    setSaving(true);
    
    // Save Tools
    if (activeTab === 'Tools' || allTools.length > 0) {
      await updateAgentTools(agentName, disabledTools);
    }

    // Save Skills
    if (activeTab === 'Skills' || allSkills.length > 0) {
      await updateAgentSkills(agentName, disabledSkills);
    }
    
    // Save General
    await updateAgentSettings(agentName, { AI_NAME: displayName });
    
    setSaving(false);
    if (onSettingsUpdated) {
      onSettingsUpdated(agentName, { AI_NAME: displayName });
    }
    onClose();
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
        width: '850px',
        height: '600px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid var(--glass-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: 'var(--bg-main)'
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-main)' }}>
              Agent Settings
            </h2>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Agent: <span style={{ color: 'var(--accent-primary)', fontWeight: '600' }}>{agentName}</span>
            </div>
          </div>
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

        {/* Content Area with Sidebar */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          
          {/* Settings Sidebar */}
          <div style={{
            width: '200px',
            backgroundColor: 'var(--bg-sidebar)',
            borderRight: '1px solid var(--glass-border)',
            display: 'flex',
            flexDirection: 'column',
            padding: '10px 0'
          }}>
            {['General', 'Tools', 'Skills'].map(tab => (
              <div 
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '12px 20px',
                  cursor: 'pointer',
                  color: activeTab === tab ? 'var(--text-main)' : 'var(--text-muted)',
                  backgroundColor: activeTab === tab ? 'var(--bg-surface-hover)' : 'transparent',
                  borderLeft: activeTab === tab ? '4px solid var(--accent-primary)' : '4px solid transparent',
                  fontWeight: activeTab === tab ? '600' : '400',
                  transition: 'all 0.2s'
                }}
              >
                {tab}
              </div>
            ))}
          </div>

          {/* Main Settings Panel */}
          <div style={{ flex: 1, padding: '20px', overflowY: 'auto', backgroundColor: 'var(--bg-main)' }}>
            
            {activeTab === 'General' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <h3 style={{ margin: 0, color: 'var(--text-main)', fontSize: '1.1rem' }}>General Settings</h3>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ color: 'var(--text-main)', fontSize: '0.9rem', fontWeight: '500' }}>
                    Agent Display Name
                  </label>
                  <input 
                    type="text" 
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Enter display name"
                    style={{
                      padding: '10px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--glass-border)',
                      backgroundColor: 'var(--bg-surface)',
                      color: 'var(--text-main)',
                      outline: 'none',
                      fontSize: '0.95rem',
                      maxWidth: '400px'
                    }}
                  />
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    This name will be displayed in the UI instead of the file name.
                  </span>
                </div>
              </div>
            )}

            {activeTab === 'Tools' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>
                <h3 style={{ margin: 0, color: 'var(--text-main)', fontSize: '1.1rem' }}>Manage Tools</h3>
                
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: '10px' }}>
                  {loadingTools ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>Loading tools...</div>
                  ) : allTools.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>No tools available.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {allTools.map(tool => {
                        const isDisabled = disabledTools.includes(tool);
                        const isRestartNeeded = needsRestart.includes(tool);
                        return (
                          <div key={tool} style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 16px',
                            backgroundColor: 'var(--bg-surface)',
                            borderRadius: '8px',
                            border: '1px solid var(--glass-border)',
                            transition: 'border-color 0.2s',
                            cursor: 'pointer'
                          }}
                          onClick={() => handleToggleTool(tool)}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <div style={{
                                width: '40px',
                                height: '22px',
                                backgroundColor: isDisabled ? 'var(--bg-main)' : 'var(--accent-success)',
                                borderRadius: '12px',
                                position: 'relative',
                                transition: 'background-color 0.3s'
                              }}>
                                <div style={{
                                  width: '18px',
                                  height: '18px',
                                  backgroundColor: '#fff',
                                  borderRadius: '50%',
                                  position: 'absolute',
                                  top: '2px',
                                  left: isDisabled ? '2px' : '20px',
                                  transition: 'left 0.3s',
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                                }} />
                              </div>
                              <div>
                                <div style={{ color: 'var(--text-main)', fontWeight: '500' }}>{tool}</div>
                                {isRestartNeeded && (
                                  <div style={{ fontSize: '0.75rem', color: 'var(--accent-warning)', marginTop: '2px' }}>
                                    Needs restart to activate
                                  </div>
                                )}
                              </div>
                            </div>
                            <div style={{ fontSize: '0.85rem', color: isDisabled ? 'var(--text-muted)' : 'var(--accent-success)' }}>
                              {isDisabled ? 'Disabled' : 'Enabled'}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'Skills' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>
                <h3 style={{ margin: 0, color: 'var(--text-main)', fontSize: '1.1rem' }}>Manage Skills</h3>
                
                <div style={{ flex: 1, overflowY: 'auto', paddingRight: '10px' }}>
                  {loadingSkills ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>Loading skills...</div>
                  ) : allSkills.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>No skills available.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {allSkills.map(skill => {
                        const isDisabled = disabledSkills.includes(skill);
                        return (
                          <div key={skill} style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 16px',
                            backgroundColor: 'var(--bg-surface)',
                            borderRadius: '8px',
                            border: '1px solid var(--glass-border)',
                            transition: 'border-color 0.2s',
                            cursor: 'pointer'
                          }}
                          onClick={() => handleToggleSkill(skill)}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <div style={{
                                width: '40px',
                                height: '22px',
                                backgroundColor: isDisabled ? 'var(--bg-main)' : 'var(--accent-success)',
                                borderRadius: '12px',
                                position: 'relative',
                                transition: 'background-color 0.3s'
                              }}>
                                <div style={{
                                  width: '18px',
                                  height: '18px',
                                  backgroundColor: '#fff',
                                  borderRadius: '50%',
                                  position: 'absolute',
                                  top: '2px',
                                  left: isDisabled ? '2px' : '20px',
                                  transition: 'left 0.3s',
                                  boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                                }} />
                              </div>
                              <div>
                                <div style={{ color: 'var(--text-main)', fontWeight: '500' }}>{skill}</div>
                              </div>
                            </div>
                            <div style={{ fontSize: '0.85rem', color: isDisabled ? 'var(--text-muted)' : 'var(--accent-success)' }}>
                              {isDisabled ? 'Disabled' : 'Enabled'}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
            
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
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '8px 16px',
              backgroundColor: 'var(--accent-primary)',
              border: 'none',
              color: '#fff',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: '500',
              opacity: saving ? 0.7 : 1
            }}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
