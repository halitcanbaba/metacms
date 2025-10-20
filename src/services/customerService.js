/**
 * Customer Service - API calls for customer management
 */
import api from './api';

const customerService = {
  /**
   * Get all customers with pagination
   */
  async getAll(params = {}) {
    const response = await api.get('/api/customers', { params });
    return response.data;
  },

  /**
   * Get customer by ID
   */
  async getById(id) {
    const response = await api.get(`/api/customers/${id}`);
    return response.data;
  },

  /**
   * Create new customer
   */
  async create(customerData) {
    const response = await api.post('/api/customers', customerData);
    return response.data;
  },

  /**
   * Update customer
   */
  async update(id, customerData) {
    const response = await api.put(`/api/customers/${id}`, customerData);
    return response.data;
  },

  /**
   * Delete customer
   */
  async delete(id) {
    await api.delete(`/api/customers/${id}`);
  },

  /**
   * Get customer positions
   */
  async getPositions(id, symbol = null) {
    const params = symbol ? { symbol } : {};
    const response = await api.get(`/api/customers/${id}/positions`, { params });
    return response.data;
  },
};

export default customerService;
