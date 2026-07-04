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

export const sendMessage = async (text, agentName) => {
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
      }),
    });
    if (!response.ok) throw new Error('Failed to send message');
    return true;
  } catch (error) {
    console.error('API Error (sendMessage):', error);
    return false;
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
