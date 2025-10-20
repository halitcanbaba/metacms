/**
 * MT5 Account Service - API calls for MT5 account management
 */
import api from './api';

const accountService = {
  /**
   * Get all accounts
   */
  async getAll(params = {}) {
    const response = await api.get('/api/accounts', { params });
    return response.data;
  },

  /**
   * Get account by login
   */
  async getByLogin(login) {
    const response = await api.get(`/api/accounts/${login}`);
    return response.data;
  },

  /**
   * Create new MT5 account
   */
  async create(accountData) {
    const response = await api.post('/api/accounts', accountData);
    return response.data;
  },

  /**
   * Update account
   */
  async update(login, accountData) {
    const response = await api.put(`/api/accounts/${login}`, accountData);
    return response.data;
  },

  /**
   * Change account password
   */
  async changePassword(login, passwordData) {
    const response = await api.post(`/api/accounts/${login}/change-password`, passwordData);
    return response.data;
  },
};

export default accountService;
