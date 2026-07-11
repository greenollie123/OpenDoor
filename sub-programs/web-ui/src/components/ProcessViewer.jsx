import React, { useState, useEffect } from 'react';
import { fetchProcessViewerData, fetchToolExecution } from '../api';

const ProcessViewer = ({ isOpen, onClose, selectedToolId, onSelectTool }) => {
  const [data, setData] = useState({ background_processes: [], tool_executions: [] });
  const [toolDetails, setToolDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    let interval;
    if (isOpen) {
      const loadData = async () => {
        const result = await fetchProcessViewerData();
        setData(result);
      };
      loadData();
      interval = setInterval(loadData, 2000);
    }
    return () => clearInterval(interval);
  }, [isOpen]);

  useEffect(() => {
    if (selectedToolId) {
      const loadDetails = async () => {
        setLoadingDetails(true);
        const result = await fetchToolExecution(selectedToolId);
        if (result && result.status === 'success') {
          setToolDetails(result.tool_execution);
        }
        setLoadingDetails(false);
      };
      loadDetails();
    } else {
      setToolDetails(null);
    }
  }, [selectedToolId]);

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      width: '400px',
      height: '100%',
      backgroundColor: 'var(--bg-main)',
      borderLeft: '1px solid var(--glass-border)',
      boxShadow: '-4px 0 20px rgba(0,0,0,0.5)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 1000,
      color: 'var(--text-main)',
      overflowY: 'auto'
    }}>
      <div style={{ padding: '20px', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', top: 0, backgroundColor: 'var(--bg-main)', zIndex: 10 }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--accent-primary)' }}>
          {selectedToolId ? 'Tool Details' : 'Process Viewer'}
        </h2>
        <button onClick={() => {
            if (selectedToolId) onSelectTool(null);
            else onClose();
        }} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>
          {selectedToolId ? '←' : '×'}
        </button>
      </div>

      <div style={{ padding: '20px', flex: 1 }}>
        {selectedToolId ? (
          loadingDetails ? <p>Loading details...</p> :
          toolDetails ? (
            <div>
              <div style={{ marginBottom: '15px' }}>
                <span style={{ fontWeight: 'bold' }}>Tool:</span> <span style={{ color: 'var(--accent-primary)'}}>{toolDetails.tool}</span>
              </div>
              <div style={{ marginBottom: '15px' }}>
                <span style={{ fontWeight: 'bold' }}>Status:</span> 
                <span style={{
                  marginLeft: '8px',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '0.85rem',
                  backgroundColor: toolDetails.status === 'running' ? 'var(--accent-warning)' : 
                                   toolDetails.status === 'error' ? 'var(--accent-danger)' : 'var(--accent-success)',
                  color: '#fff',
                  fontWeight: '600'
                }}>
                  {toolDetails.status}
                </span>
              </div>
              <div style={{ marginBottom: '15px' }}>
                <span style={{ fontWeight: 'bold' }}>Agent:</span> {toolDetails.agent}
              </div>
              <div style={{ marginBottom: '15px' }}>
                <span style={{ fontWeight: 'bold' }}>Started:</span> {new Date(toolDetails.start_time).toLocaleString()}
              </div>
              {toolDetails.end_time && (
                <div style={{ marginBottom: '15px' }}>
                  <span style={{ fontWeight: 'bold' }}>Ended:</span> {new Date(toolDetails.end_time).toLocaleString()}
                </div>
              )}
              <div style={{ marginBottom: '15px' }}>
                <span style={{ fontWeight: 'bold' }}>Arguments:</span>
                <pre style={{ backgroundColor: 'var(--bg-surface)', padding: '10px', borderRadius: '6px', overflowX: 'auto', fontSize: '0.85rem', marginTop: '8px', border: '1px solid var(--glass-border)' }}>
                  {JSON.stringify(toolDetails.args, null, 2)}
                </pre>
              </div>

              {toolDetails.subagent_events && toolDetails.subagent_events.length > 0 && (
                <div style={{ marginBottom: '15px' }}>
                  <span style={{ fontWeight: 'bold' }}>Sub-Agent Activity:</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '10px' }}>
                    {toolDetails.subagent_events.map((event, idx) => (
                      <div key={idx} style={{ padding: '12px', borderRadius: '8px', backgroundColor: 'var(--bg-surface)', border: '1px solid var(--glass-border)' }}>
                        {event.type === 'thought' ? (
                          <>
                            <div style={{ fontWeight: '600', color: 'var(--text-muted)', marginBottom: '6px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span>🧠</span> Thinking
                            </div>
                            <div style={{ fontSize: '0.85rem', whiteSpace: 'pre-wrap', color: 'var(--text-main)', lineHeight: '1.4' }}>{event.content}</div>
                          </>
                        ) : (
                          <>
                            <div style={{ fontWeight: '600', color: 'var(--accent-primary)', marginBottom: '6px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span>⚙️</span> Running {event.tool}
                            </div>
                            <pre style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', backgroundColor: 'var(--bg-main)', padding: '8px', borderRadius: '6px', border: '1px solid var(--glass-border)', overflowX: 'auto' }}>
                              {JSON.stringify(event.args, null, 2)}
                            </pre>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {toolDetails.error && (
                <div style={{ marginBottom: '15px' }}>
                  <span style={{ fontWeight: 'bold', color: 'var(--accent-danger)' }}>Error:</span>
                  <pre style={{ backgroundColor: 'rgba(255,50,50,0.1)', padding: '10px', borderRadius: '6px', overflowX: 'auto', fontSize: '0.85rem', marginTop: '8px', border: '1px solid var(--accent-danger)', color: 'var(--accent-danger)' }}>
                    {toolDetails.error}
                  </pre>
                </div>
              )}
              {toolDetails.output && (
                <div style={{ marginBottom: '15px' }}>
                  <span style={{ fontWeight: 'bold' }}>Output:</span>
                  <pre style={{ backgroundColor: 'var(--bg-surface)', padding: '10px', borderRadius: '6px', overflowX: 'auto', fontSize: '0.85rem', marginTop: '8px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', border: '1px solid var(--glass-border)' }}>
                    {toolDetails.output}
                  </pre>
                </div>
              )}
            </div>
          ) : <p>Failed to load details.</p>
        ) : (
          <>
            <h3 style={{ fontSize: '1.05rem', color: 'var(--text-main)', marginBottom: '15px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '5px' }}>Background Processes</h3>
            {data.background_processes.length === 0 ? <p style={{ color: 'var(--text-muted)' }}>No background processes.</p> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '30px' }}>
                {data.background_processes.map((proc, idx) => (
                  <div key={idx} style={{ backgroundColor: 'var(--bg-surface)', padding: '14px', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: '600' }}>{proc.name}</span>
                      <span style={{
                        padding: '2px 10px',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: '600',
                        backgroundColor: proc.status === 'Running' ? 'var(--accent-success)' : 'var(--text-muted)',
                        color: '#fff'
                      }}>{proc.status}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>PID: {proc.pid}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', opacity: 0.7 }}>{proc.command}</div>
                  </div>
                ))}
              </div>
            )}

            <h3 style={{ fontSize: '1.05rem', color: 'var(--text-main)', marginBottom: '15px', borderBottom: '1px solid var(--glass-border)', paddingBottom: '5px' }}>Recent Tool Executions</h3>
            {data.tool_executions.length === 0 ? <p style={{ color: 'var(--text-muted)' }}>No recent tool executions.</p> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {data.tool_executions.map(ex => (
                  <div 
                    key={ex.id} 
                    onClick={() => onSelectTool(ex.id)}
                    style={{ backgroundColor: 'var(--bg-surface)', padding: '14px', borderRadius: '8px', border: '1px solid var(--glass-border)', cursor: 'pointer', transition: 'all 0.2s' }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'var(--accent-primary)';
                      e.currentTarget.style.transform = 'translateY(-2px)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--glass-border)';
                      e.currentTarget.style.transform = 'translateY(0)';
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: '600', color: 'var(--accent-primary)' }}>{ex.tool}</span>
                      <span style={{
                        padding: '2px 10px',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: '600',
                        backgroundColor: ex.status === 'running' ? 'var(--accent-warning)' : 
                                         ex.status === 'error' ? 'var(--accent-danger)' : 'var(--accent-success)',
                        color: '#fff'
                      }}>{ex.status}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Agent: {ex.agent}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{new Date(ex.start_time).toLocaleTimeString()}</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default ProcessViewer;
