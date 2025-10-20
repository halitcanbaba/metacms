import api from './api';

/**
 * Agent Service
 * Handles all agent-related API calls
 */

/**
 * Get all agents with pagination and optional search
 */
export const getAgents = async (params = {}) => {
  const { search, active_only, skip = 0, limit = 100 } = params;
  
  const queryParams = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });

  if (search) {
    queryParams.append('search', search);
  }

  if (active_only !== undefined) {
    queryParams.append('active_only', active_only.toString());
  }

  const response = await api.get(`/api/agents?${queryParams}`);
  return response.data;
};

/**
 * Get agent by ID
 */
export const getAgentById = async (agentId) => {
  const response = await api.get(`/api/agents/${agentId}`);
  return response.data;
};

/**
 * Create a new agent
 */
export const createAgent = async (agentData) => {
  const response = await api.post('/api/agents', agentData);
  return response.data;
};

/**
 * Update an existing agent
 */
export const updateAgent = async (agentId, agentData) => {
  const response = await api.patch(`/api/agents/${agentId}`, agentData);
  return response.data;
};

/**
 * Delete an agent
 */
export const deleteAgent = async (agentId) => {
  await api.delete(`/api/agents/${agentId}`);
};

/**
 * Get customers by agent ID
 */
export const getCustomersByAgent = async (agentId, params = {}) => {
  const { skip = 0, limit = 100 } = params;
  
  const queryParams = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });

  const response = await api.get(`/api/customers/by-agent/${agentId}?${queryParams}`);
  return response.data;
};

const agentsService = {
  getAgents,
  getAgentById,
  createAgent,
  updateAgent,
  deleteAgent,
  getCustomersByAgent,
};

export default agentsService;
