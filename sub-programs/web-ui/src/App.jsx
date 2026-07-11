import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import MessageInput from './components/MessageInput';
import { fetchAgents, loadAgent, fetchUpdates, sendMessage, approveCommand } from './api';
import ProcessViewer from './components/ProcessViewer';

// Helper to get a cookie value by name
const getCookie = (name) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(';').shift());
  return null;
};

// Helper to set a cookie value
const setCookie = (name, value, days = 365) => {
  const date = new Date();
  date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
  const expires = `; expires=${date.toUTCString()}`;
  document.cookie = `${name}=${encodeURIComponent(value)}${expires}; path=/; SameSite=Lax`;
};

function App() {
  const [agents, setAgents] = useState([]);
  const [agentDetails, setAgentDetails] = useState({});
  const [currentAgent, setCurrentAgent] = useState('Terry');
  const [histories, setHistories] = useState({}); // { [agentName]: { messages: [], lastUpdateId: 0, hasLoaded: false } }
  const [status, setStatus] = useState('Connecting...');
  
  // Process Viewer State
  const [showProcessViewer, setShowProcessViewer] = useState(false);
  const [selectedToolId, setSelectedToolId] = useState(null);

  // Helper to parse raw backend updates
  const parseUpdates = (updates, agentName) => {
    return updates
      .map(u => ({
        type: u.type,
        channel: u.channel,
        content: u.content,
        id: u.id,
        agent: u.type === 'agent' || u.type === 'assistant' ? agentName : null,
        approval_id: u.approval_id,
        decision: u.decision,
        title: u.title,
        description: u.description,
        tool_call_id: u.tool_call_id
      }))
      .filter(u => u.content !== 'CLEAR');
  };

  // Helper to get max update ID
  const getMaxId = (updates) => {
    return updates.reduce((max, u) => Math.max(max, u.id + 1), 0);
  };

  // 1. Initial Load: Fetch agents list and start preloading histories
  useEffect(() => {
    const initApp = async () => {
      setStatus('Fetching agents...');
      const data = await fetchAgents();
      const agentsList = data.agents || [];
      const details = data.agent_details || {};
      
      if (agentsList.length > 0) {
        setAgents(agentsList);
        setAgentDetails(details);
        
        // Select the initial agent (default to saved cookie, Terry, or the first available)
        const savedAgent = getCookie('last_selected_agent');
        const initialAgent = (savedAgent && agentsList.includes(savedAgent))
          ? savedAgent
          : (agentsList.includes('Terry') ? 'Terry' : agentsList[0]);
        setCurrentAgent(initialAgent);
        
        // Save the selection back to cookie
        setCookie('last_selected_agent', initialAgent);
        
        setStatus(`Loading ${initialAgent}...`);
        
        // Load the initial agent first so the user can start using it immediately
        await loadAgent(initialAgent);
        const initialUpdates = await fetchUpdates(0, initialAgent);
        
        setHistories(prev => ({
          ...prev,
          [initialAgent]: {
            messages: parseUpdates(initialUpdates, initialAgent),
            lastUpdateId: getMaxId(initialUpdates),
            hasLoaded: true
          }
        }));
        
        setStatus('Connected');

        // Now preload the remaining agents in the background
        const remainingAgents = agentsList.filter(a => a !== initialAgent);
        for (const agent of remainingAgents) {
          try {
            await loadAgent(agent);
            const updates = await fetchUpdates(0, agent);
            setHistories(prev => ({
              ...prev,
              [agent]: {
                messages: parseUpdates(updates, agent),
                lastUpdateId: getMaxId(updates),
                hasLoaded: true
              }
            }));
          } catch (e) {
            console.error(`Failed to preload background agent ${agent}`, e);
          }
        }
        
        // Restore context to the active initial agent on backend
        await loadAgent(initialAgent);
      } else {
        setStatus('No agents found. Backend down?');
      }
    };
    
    initApp();
  }, []);

  // 2. Poll for updates for the current active agent
  useEffect(() => {
    let intervalId;
    
    const poll = async () => {
      const currentHist = histories[currentAgent];
      if (!currentHist || !currentHist.hasLoaded) return;
      
      const newUpdates = await fetchUpdates(currentHist.lastUpdateId, currentAgent);
      if (newUpdates && newUpdates.length > 0) {
        let newMessages = [...currentHist.messages];
        let newId = currentHist.lastUpdateId;
        
        newUpdates.forEach(update => {
          if (update.content === 'CLEAR') {
            newMessages = [];
          } else {
            // Deduplicate user messages
            if (update.type === 'user') {
              const optIndex = newMessages.findIndex(msg => msg.optimistic && msg.content === update.content);
              if (optIndex !== -1) {
                newMessages[optIndex] = {
                  type: update.type,
                  channel: update.channel,
                  content: update.content,
                  id: update.id
                };
                newId = Math.max(newId, update.id + 1);
                return;
              }
            }
            
            newMessages.push({
              type: update.type,
              channel: update.channel,
              content: update.content,
              id: update.id,
              agent: update.type === 'agent' || update.type === 'assistant' ? currentAgent : null,
              approval_id: update.approval_id,
              decision: update.decision,
              title: update.title,
              description: update.description,
              tool_call_id: update.tool_call_id
            });
          }
          newId = Math.max(newId, update.id + 1);
        });
        
        setHistories(prev => ({
          ...prev,
          [currentAgent]: {
            ...prev[currentAgent],
            messages: newMessages,
            lastUpdateId: newId
          }
        }));
      }
    };

    // Only start polling once the app is initialized and active agent is loaded
    if (agents.length > 0 && histories[currentAgent]?.hasLoaded) {
      intervalId = setInterval(poll, 1000);
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [currentAgent, histories, agents]);

  // Handle agent selection
  const handleSelectAgent = async (agent) => {
    if (agent === currentAgent) return;
    
    // Switch UI context immediately since it is cached
    setCurrentAgent(agent);
    setCookie('last_selected_agent', agent);
    setStatus(`Connecting to ${agent}...`);
    
    // Notify backend
    const success = await loadAgent(agent);
    if (success) {
      setStatus('Connected');
      
      // Fetch any missed updates immediately
      const currentHist = histories[agent];
      if (currentHist) {
        const newUpdates = await fetchUpdates(currentHist.lastUpdateId, agent);
        if (newUpdates && newUpdates.length > 0) {
          let newMessages = [...currentHist.messages];
          let newId = currentHist.lastUpdateId;
          
          newUpdates.forEach(update => {
            if (update.content === 'CLEAR') {
              newMessages = [];
            } else {
              newMessages.push({
                type: update.type,
                channel: update.channel,
                content: update.content,
                id: update.id,
                agent: update.type === 'agent' || update.type === 'assistant' ? agent : null,
                approval_id: update.approval_id,
                decision: update.decision,
                title: update.title,
                description: update.description,
                tool_call_id: update.tool_call_id
              });
            }
            newId = Math.max(newId, update.id + 1);
          });
          
          setHistories(prev => ({
            ...prev,
            [agent]: {
              ...prev[agent],
              messages: newMessages,
              lastUpdateId: newId
            }
          }));
        }
      }
    } else {
      setStatus(`Failed to switch to ${agent}`);
    }
  };

  // Handle sending a message
  const handleSendMessage = async (text, mediaPaths = []) => {
    const tempId = Date.now();
    
    // Optimistic UI update: append to the current agent's history in the cache
    setHistories(prev => {
      const currentHist = prev[currentAgent] || { messages: [], lastUpdateId: 0, hasLoaded: true };
      return {
        ...prev,
        [currentAgent]: {
          ...currentHist,
          messages: [...currentHist.messages, {
            type: 'user',
            channel: 'Web',
            content: text,
            optimistic: true,
            tempId: tempId
          }]
        }
      };
    });
    
    const success = await sendMessage(text, currentAgent, mediaPaths);
    if (!success) {
      // Remove optimistic message and add system error
      setHistories(prev => {
        const currentHist = prev[currentAgent];
        if (!currentHist) return prev;
        return {
          ...prev,
          [currentAgent]: {
            ...currentHist,
            messages: currentHist.messages
              .filter(msg => msg.tempId !== tempId)
              .concat({
                type: 'system',
                content: 'Failed to send message to backend.'
              })
          }
        };
      });
    }
  };

  const handleApproveCommand = async (approvalId) => {
    const success = await approveCommand(approvalId, 'approved');
    if (success) {
      setHistories(prev => {
        const currentHist = prev[currentAgent];
        if (!currentHist) return prev;
        const updatedMessages = currentHist.messages.map(msg => {
          if (msg.approval_id === approvalId) {
            return { ...msg, decision: 'approved' };
          }
          return msg;
        });
        return {
          ...prev,
          [currentAgent]: {
            ...currentHist,
            messages: updatedMessages
          }
        };
      });
    }
  };

  const handleDenyCommand = async (approvalId) => {
    const success = await approveCommand(approvalId, 'denied');
    if (success) {
      setHistories(prev => {
        const currentHist = prev[currentAgent];
        if (!currentHist) return prev;
        const updatedMessages = currentHist.messages.map(msg => {
          if (msg.approval_id === approvalId) {
            return { ...msg, decision: 'denied' };
          }
          return msg;
        });
        return {
          ...prev,
          [currentAgent]: {
            ...currentHist,
            messages: updatedMessages
          }
        };
      });
    }
  };

  const currentMessages = histories[currentAgent]?.messages || [];

  return (
    <div style={{
      display: 'flex',
      height: '100%',
      width: '100%',
      backgroundColor: 'var(--bg-main)',
    }}>
      <Sidebar 
        agents={agents} 
        agentDetails={agentDetails}
        currentAgent={currentAgent} 
        onSelectAgent={handleSelectAgent} 
      />
      
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        position: 'relative'
      }}>
        {/* Header bar */}
        <div style={{
          height: '60px',
          borderBottom: '1px solid var(--glass-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          backgroundColor: 'var(--bg-sidebar)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h1 style={{ fontSize: '1.2rem', fontWeight: '600' }}>
              {agentDetails[currentAgent]?.AI_NAME || currentAgent}
            </h1>
            <span style={{ 
              fontSize: '0.8rem', 
              color: status.includes('Failed') ? 'var(--accent-danger)' : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <div style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: status.includes('Connected') || status === 'Preloading histories...' ? 'var(--accent-success)' : 'var(--accent-warning)'
              }}></div>
            </span>
          </div>
          <button 
            onClick={() => setShowProcessViewer(!showProcessViewer)}
            style={{
              padding: '6px 14px',
              backgroundColor: showProcessViewer ? 'var(--accent-primary)' : 'var(--bg-surface)',
              color: showProcessViewer ? 'var(--bg-main)' : 'var(--text-main)',
              border: `1px solid ${showProcessViewer ? 'var(--accent-primary)' : 'var(--glass-border)'}`,
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: '600',
              transition: 'all 0.2s',
              fontSize: '0.85rem'
            }}
          >
            {showProcessViewer ? 'Close Processes' : 'View Processes'}
          </button>
        </div>

        {/* Main Chat Area */}
        <ChatArea 
          history={currentMessages} 
          agentDetails={agentDetails} 
          onApprove={handleApproveCommand}
          onDeny={handleDenyCommand}
          onToolClick={(toolId) => {
            setSelectedToolId(toolId);
            setShowProcessViewer(true);
          }}
        />

        {/* Input Area */}
        <MessageInput 
          onSend={handleSendMessage} 
          currentAgent={currentAgent} 
          agentDetails={agentDetails} 
        />
      </div>

      <ProcessViewer 
        isOpen={showProcessViewer} 
        onClose={() => setShowProcessViewer(false)}
        selectedToolId={selectedToolId}
        onSelectTool={setSelectedToolId}
      />
    </div>
  );
}

export default App;
