/**
 * Customers API Service
 */
import api from './api';

export const customersService = {
  /**
   * Get all customers with pagination and search
   */
  getAll: async (params = {}) => {
    const response = await api.get('/api/customers', { params });
    return response.data;
  },

  /**
   * Get customer by ID
   */
  getById: async (id) => {
    const response = await api.get(`/api/customers/${id}`);
    return response.data;
  },

  /**
   * Create new customer
   */
  create: async (data) => {
    const response = await api.post('/api/customers', data);
    return response.data;
  },

  /**
   * Update customer
   */
  update: async (id, data) => {
    const response = await api.put(`/api/customers/${id}`, data);
    return response.data;
  },

  /**
   * Delete customer
   */
  delete: async (id) => {
    await api.delete(`/api/customers/${id}`);
  },

  /**
   * Get customer positions
   */
  getPositions: async (id, symbol = null) => {
    const params = symbol ? { symbol } : {};
    const response = await api.get(`/api/customers/${id}/positions`, { params });
    return response.data;
  },
};
