const BASE_URL = '/api';

export const fetchAgents = async () => {
  try {
    const response = await fetch(`${BASE_URL}/agents`);
    if (!response.ok) throw new Error('Failed to fetch agents');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('API Error (fetchAgents):', error);
    return { agents: [], agent_details: {} };
  }
};

export const loadAgent = async (agentName) => {
  try {
    const response = await fetch(`${BASE_URL}/load_agent?agent=${encodeURIComponent(agentName)}`);
    if (!response.ok) throw new Error('Failed to load agent');
    return true;
  } catch (error) {
    console.error('API Error (loadAgent):', error);
    return false;
  }
};

export const fetchUpdates = async (since, agentName) => {
  try {
    const response = await fetch(`${BASE_URL}/updates?since=${since}&agent=${encodeURIComponent(agentName)}`);
    if (!response.ok) throw new Error('Failed to fetch updates');
    const data = await response.json();
    return data.updates || [];
  } catch (error) {
    // Suppress polling errors in console to avoid spam
    return [];
  }
};

export const sendMessage = async (text, agentName, mediaPaths = []) => {
  try {
    const response = await fetch(`${BASE_URL}/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        channel: 'Web',
        text: text,
        agent: agentName,
        media_paths: mediaPaths,
      }),
    });
    if (!response.ok) throw new Error('Failed to send message');
    return true;
  } catch (error) {
    console.error('API Error (sendMessage):', error);
    return false;
  }
};

export const uploadFile = async (file, agentName) => {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('agent', agentName);
    
    const response = await fetch(`${BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) throw new Error('Failed to upload file');
    return await response.json();
  } catch (error) {
    console.error('API Error (uploadFile):', error);
    return null;
  }
};

export const fetchAgentTools = async (agentName) => {
  try {
    const response = await fetch(`${BASE_URL}/agent_tools?agent=${encodeURIComponent(agentName)}`);
    if (!response.ok) throw new Error('Failed to fetch tools');
    return await response.json();
  } catch (error) {
    console.error('API Error (fetchAgentTools):', error);
    return { all_tools: [], disabled_tools: [], needs_restart: [] };
  }
};

export const updateAgentTools = async (agentName, disabledTools) => {
  try {
    const response = await fetch(`${BASE_URL}/agent_tools`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        agent: agentName,
        disabled_tools: disabledTools,
      }),
    });
    if (!response.ok) throw new Error('Failed to update tools');
    return true;
  } catch (error) {
    console.error('API Error (updateAgentTools):', error);
    return false;
  }
};

export const createAgent = async (agentName, agentDisplayName) => {
  try {
    const response = await fetch(`${BASE_URL}/create_agent`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        agent_name: agentName,
        agent_display_name: agentDisplayName || agentName,
      }),
    });
    if (!response.ok) throw new Error('Failed to create agent');
    return await response.json();
  } catch (error) {
    console.error('API Error (createAgent):', error);
    return false;
  }
};

export const updateAgentSettings = async (agentName, settings) => {
  try {
    const response = await fetch(`${BASE_URL}/agent_settings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        agent: agentName,
        settings: settings,
      }),
    });
    if (!response.ok) throw new Error('Failed to update agent settings');
    return await response.json();
  } catch (error) {
    console.error('API Error (updateAgentSettings):', error);
    return false;
  }
};

export const fetchAgentSkills = async (agentName) => {
  try {
    const response = await fetch(`${BASE_URL}/agent_skills?agent=${encodeURIComponent(agentName)}`);
    if (!response.ok) throw new Error('Failed to fetch skills');
    return await response.json();
  } catch (error) {
    console.error('API Error (fetchAgentSkills):', error);
    return { all_skills: [], disabled_skills: [] };
  }
};

export const updateAgentSkills = async (agentName, disabledSkills) => {
  try {
    const response = await fetch(`${BASE_URL}/agent_skills`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        agent: agentName,
        disabled_skills: disabledSkills,
      }),
    });
    if (!response.ok) throw new Error('Failed to update skills');
    return true;
  } catch (error) {
    console.error('API Error (updateAgentSkills):', error);
    return false;
  }
};

export const approveCommand = async (approvalId, action) => {
  try {
    const response = await fetch(`${BASE_URL}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        approval_id: approvalId,
        action: action, // "approved" or "denied"
      }),
    });
    if (!response.ok) throw new Error('Failed to submit command approval');
    return true;
  } catch (error) {
    console.error('API Error (approveCommand):', error);
    return false;
  }
};

export const fetchProcessViewerData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/process_viewer`);
    if (!response.ok) throw new Error('Failed to fetch process viewer data');
    return await response.json();
  } catch (error) {
    console.error('API Error (fetchProcessViewerData):', error);
    return { background_processes: [], tool_executions: [] };
  }
};

export const fetchToolExecution = async (id) => {
  try {
    const response = await fetch(`${BASE_URL}/tool_execution/${id}`);
    if (!response.ok) throw new Error('Failed to fetch tool execution data');
    return await response.json();
  } catch (error) {
    console.error('API Error (fetchToolExecution):', error);
    return null;
  }
};
