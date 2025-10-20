/**
 * MT5 Accounts API Service
 */
import api from './api';

export const accountsService = {
  /**
   * Get all MT5 accounts
   */
  getAll: async (params = {}) => {
    // Add refresh_balance=true to get live MT5 balances
    const response = await api.get('/api/accounts', { 
      params: { ...params, refresh_balance: true } 
    });
    return response.data;
  },

  /**
   * Get account by login
   */
  getByLogin: async (login) => {
    const response = await api.get(`/api/accounts/${login}`);
    return response.data;
  },

  /**
   * Create new MT5 account
   */
  create: async (data) => {
    const response = await api.post('/api/accounts', data);
    return response.data;
  },

  /**
   * Update account
   */
  update: async (login, data) => {
    const response = await api.put(`/api/accounts/${login}`, data);
    return response.data;
  },

  /**
   * Delete account
   */
  delete: async (login) => {
    await api.delete(`/api/accounts/${login}`);
  },

  /**
   * Get available MT5 groups
   */
  getGroups: async () => {
    const response = await api.get('/api/accounts/groups');
    return response.data;
  },
};
