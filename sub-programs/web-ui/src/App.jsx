import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import MessageInput from './components/MessageInput';
import { fetchAgents, loadAgent, fetchUpdates, sendMessage } from './api';

function App() {
  const [agents, setAgents] = useState([]);
  const [agentDetails, setAgentDetails] = useState({});
  const [currentAgent, setCurrentAgent] = useState('Terry');
  const [histories, setHistories] = useState({}); // { [agentName]: { messages: [], lastUpdateId: 0, hasLoaded: false } }
  const [status, setStatus] = useState('Connecting...');

  // Helper to parse raw backend updates
  const parseUpdates = (updates, agentName) => {
    return updates
      .map(u => ({
        type: u.type,
        channel: u.channel,
        content: u.content,
        id: u.id,
        agent: u.type === 'agent' || u.type === 'assistant' ? agentName : null
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
        
        // Select the initial agent (default to Terry or the first available)
        const initialAgent = agentsList.includes('Terry') ? 'Terry' : agentsList[0];
        setCurrentAgent(initialAgent);
        
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
              agent: update.type === 'agent' || update.type === 'assistant' ? currentAgent : null
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
                agent: update.type === 'agent' || update.type === 'assistant' ? agent : null
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
  const handleSendMessage = async (text) => {
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
    
    const success = await sendMessage(text, currentAgent);
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
              {status}
            </span>
          </div>
          {/* <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Port: 5050 Webhook
          </div> */}
        </div>

        {/* Main Chat Area */}
        <ChatArea history={currentMessages} agentDetails={agentDetails} />

        {/* Input Area */}
        <MessageInput 
          onSend={handleSendMessage} 
          currentAgent={currentAgent} 
          agentDetails={agentDetails} 
        />
      </div>
    </div>
  );
}

export default App;
