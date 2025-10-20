/**
 * Balance Operations API Service
 */
import api from './api';

export const balanceService = {
  /**
   * Get balance operations history
   */
  getHistory: async (params = {}) => {
    const response = await api.get('/api/balance', { params });
    return response.data;
  },

  /**
   * Create balance operation (deposit, withdrawal, credit_in, credit_out)
   */
  createOperation: async (data) => {
    const response = await api.post('/api/balance', data);
    return response.data;
  },

  /**
   * Create credit operation (positive = credit_in, negative = credit_out)
   */
  createCredit: async (login, amount, comment) => {
    const response = await api.post('/api/balance/credit', null, {
      params: { login, amount, comment },
    });
    return response.data;
  },

  /**
   * Deposit shorthand
   */
  deposit: async (login, amount, comment = '') => {
    return balanceService.createOperation({
      login,
      type: 'deposit',
      amount,
      comment,
    });
  },

  /**
   * Withdrawal shorthand
   */
  withdrawal: async (login, amount, comment = '') => {
    return balanceService.createOperation({
      login,
      type: 'withdrawal',
      amount,
      comment,
    });
  },
};
