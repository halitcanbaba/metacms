/**
 * Agents Page - List, Create, Edit, Delete agents
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  CButton,
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CForm,
  CFormInput,
  CFormLabel,
  CFormSwitch,
  CModal,
  CModalBody,
  CModalFooter,
  CModalHeader,
  CModalTitle,
  CRow,
  CSpinner,
  CTable,
  CTableBody,
  CTableDataCell,
  CTableHead,
  CTableHeaderCell,
  CTableRow,
  CAlert,
  CBadge,
  CInputGroup,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilPlus, cilPencil, cilTrash, cilSearch, cilReload, cilPeople } from '@coreui/icons';
import { getAgents, createAgent, updateAgent, deleteAgent, getCustomersByAgent } from '../services/agents';

const Agents = () => {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [showCustomersModal, setShowCustomersModal] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [selectedAgentCustomers, setSelectedAgentCustomers] = useState([]);
  const [loadingCustomers, setLoadingCustomers] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    is_active: true,
  });

  const loadAgents = useCallback(async (searchTerm = '') => {
    try {
      setLoading(true);
      setError('');
      const data = await getAgents({
        search: searchTerm || undefined,
        active_only: activeOnly,
        limit: 100,
      });
      setAgents(data.items || []);
    } catch (err) {
      setError('Failed to load agents: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, [activeOnly]); // activeOnly is a dependency since it affects the API call

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const handleSearch = () => {
    loadAgents(search);
  };

  const handleOpenModal = (agent = null) => {
    if (agent) {
      setEditingAgent(agent);
      setFormData({
        name: agent.name || '',
        email: agent.email || '',
        phone: agent.phone || '',
        is_active: agent.is_active !== false,
      });
    } else {
      setEditingAgent(null);
      setFormData({
        name: '',
        email: '',
        phone: '',
        is_active: true,
      });
    }
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingAgent(null);
    setFormData({
      name: '',
      email: '',
      phone: '',
      is_active: true,
    });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingAgent) {
        await updateAgent(editingAgent.id, formData);
        setSuccess('Agent updated successfully');
      } else {
        await createAgent(formData);
        setSuccess('Agent created successfully');
      }
      handleCloseModal();
      loadAgents(search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save agent');
    }
  };

  const handleDelete = async (agentId, agentName) => {
    if (!window.confirm(`Are you sure you want to delete agent "${agentName}"?`)) {
      return;
    }

    try {
      setError('');
      setSuccess('');
      await deleteAgent(agentId);
      setSuccess('Agent deleted successfully');
      loadAgents(search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete agent. Agent may have customers.');
    }
  };

  const handleViewCustomers = async (agent) => {
    setSelectedAgentCustomers([]);
    setLoadingCustomers(true);
    setShowCustomersModal(true);

    try {
      const data = await getCustomersByAgent(agent.id, { limit: 500 });
      setSelectedAgentCustomers(data.items || []);
    } catch (err) {
      setError('Failed to load customers: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoadingCustomers(false);
    }
  };

  return (
    <>
      <CRow>
        <CCol xs={12}>
          <CCard className="mb-4">
            <CCardHeader>
              <div className="d-flex justify-content-between align-items-center">
                <strong>Agents</strong>
                <CButton color="primary" onClick={() => handleOpenModal()}>
                  <CIcon icon={cilPlus} className="me-2" />
                  Add Agent
                </CButton>
              </div>
            </CCardHeader>
            <CCardBody>
              {error && (
                <CAlert color="danger" dismissible onClose={() => setError('')}>
                  {error}
                </CAlert>
              )}
              {success && (
                <CAlert color="success" dismissible onClose={() => setSuccess('')}>
                  {success}
                </CAlert>
              )}

              {/* Search and Filters */}
              <CRow className="mb-3">
                <CCol md={8}>
                  <CInputGroup>
                    <CFormInput
                      placeholder="Search agents by name, email, or phone..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                    />
                    <CButton color="primary" onClick={handleSearch}>
                      <CIcon icon={cilSearch} className="me-2" />
                      Search
                    </CButton>
                    <CButton color="secondary" onClick={() => { setSearch(''); loadAgents(''); }}>
                      <CIcon icon={cilReload} className="me-2" />
                      Reset
                    </CButton>
                  </CInputGroup>
                </CCol>
                <CCol md={4}>
                  <CFormSwitch
                    label="Show active only"
                    checked={activeOnly}
                    onChange={(e) => setActiveOnly(e.target.checked)}
                  />
                </CCol>
              </CRow>

              {/* Agents Table */}
              {loading ? (
                <div className="text-center py-4">
                  <CSpinner color="primary" />
                </div>
              ) : (
                <CTable hover responsive>
                  <CTableHead>
                    <CTableRow>
                      <CTableHeaderCell>ID</CTableHeaderCell>
                      <CTableHeaderCell>Name</CTableHeaderCell>
                      <CTableHeaderCell>Email</CTableHeaderCell>
                      <CTableHeaderCell>Phone</CTableHeaderCell>
                      <CTableHeaderCell>Status</CTableHeaderCell>
                      <CTableHeaderCell>Created</CTableHeaderCell>
                      <CTableHeaderCell>Actions</CTableHeaderCell>
                    </CTableRow>
                  </CTableHead>
                  <CTableBody>
                    {agents.length === 0 ? (
                      <CTableRow>
                        <CTableDataCell colSpan="7" className="text-center">
                          No agents found
                        </CTableDataCell>
                      </CTableRow>
                    ) : (
                      agents.map((agent) => (
                        <CTableRow key={agent.id}>
                          <CTableDataCell>{agent.id}</CTableDataCell>
                          <CTableDataCell>
                            <strong>{agent.name}</strong>
                          </CTableDataCell>
                          <CTableDataCell>{agent.email}</CTableDataCell>
                          <CTableDataCell>{agent.phone || '-'}</CTableDataCell>
                          <CTableDataCell>
                            <CBadge color={agent.is_active ? 'success' : 'secondary'}>
                              {agent.is_active ? 'Active' : 'Inactive'}
                            </CBadge>
                          </CTableDataCell>
                          <CTableDataCell>
                            {new Date(agent.created_at).toLocaleDateString()}
                          </CTableDataCell>
                          <CTableDataCell>
                            <div className="d-flex gap-2">
                              <CButton
                                color="info"
                                size="sm"
                                onClick={() => handleViewCustomers(agent)}
                                title="View Customers"
                              >
                                <CIcon icon={cilPeople} />
                              </CButton>
                              <CButton
                                color="warning"
                                size="sm"
                                onClick={() => handleOpenModal(agent)}
                              >
                                <CIcon icon={cilPencil} />
                              </CButton>
                              <CButton
                                color="danger"
                                size="sm"
                                onClick={() => handleDelete(agent.id, agent.name)}
                              >
                                <CIcon icon={cilTrash} />
                              </CButton>
                            </div>
                          </CTableDataCell>
                        </CTableRow>
                      ))
                    )}
                  </CTableBody>
                </CTable>
              )}
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>

      {/* Create/Edit Agent Modal */}
      <CModal visible={showModal} onClose={handleCloseModal}>
        <CModalHeader>
          <CModalTitle>{editingAgent ? 'Edit Agent' : 'Create Agent'}</CModalTitle>
        </CModalHeader>
        <CForm onSubmit={handleSubmit}>
          <CModalBody>
            {error && <CAlert color="danger">{error}</CAlert>}

            <div className="mb-3">
              <CFormLabel htmlFor="name">Name *</CFormLabel>
              <CFormInput
                type="text"
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>

            <div className="mb-3">
              <CFormLabel htmlFor="email">Email *</CFormLabel>
              <CFormInput
                type="email"
                id="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
              />
            </div>

            <div className="mb-3">
              <CFormLabel htmlFor="phone">Phone</CFormLabel>
              <CFormInput
                type="tel"
                id="phone"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
            </div>

            {editingAgent && (
              <div className="mb-3">
                <CFormSwitch
                  label="Active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
              </div>
            )}
          </CModalBody>
          <CModalFooter>
            <CButton color="secondary" onClick={handleCloseModal}>
              Cancel
            </CButton>
            <CButton color="primary" type="submit">
              {editingAgent ? 'Update' : 'Create'}
            </CButton>
          </CModalFooter>
        </CForm>
      </CModal>

      {/* View Customers Modal */}
      <CModal size="lg" visible={showCustomersModal} onClose={() => setShowCustomersModal(false)}>
        <CModalHeader>
          <CModalTitle>Agent Customers</CModalTitle>
        </CModalHeader>
        <CModalBody>
          {loadingCustomers ? (
            <div className="text-center py-4">
              <CSpinner color="primary" />
            </div>
          ) : selectedAgentCustomers.length === 0 ? (
            <CAlert color="info">No customers found for this agent.</CAlert>
          ) : (
            <CTable hover responsive>
              <CTableHead>
                <CTableRow>
                  <CTableHeaderCell>ID</CTableHeaderCell>
                  <CTableHeaderCell>Name</CTableHeaderCell>
                  <CTableHeaderCell>Email</CTableHeaderCell>
                  <CTableHeaderCell>Phone</CTableHeaderCell>
                  <CTableHeaderCell>MT5 Accounts</CTableHeaderCell>
                </CTableRow>
              </CTableHead>
              <CTableBody>
                {selectedAgentCustomers.map((customer) => (
                  <CTableRow key={customer.id}>
                    <CTableDataCell>{customer.id}</CTableDataCell>
                    <CTableDataCell>
                      <strong>{customer.name}</strong>
                    </CTableDataCell>
                    <CTableDataCell>{customer.email || '-'}</CTableDataCell>
                    <CTableDataCell>{customer.phone || '-'}</CTableDataCell>
                    <CTableDataCell>
                      <CBadge color="info">{customer.mt5_accounts?.length || 0}</CBadge>
                    </CTableDataCell>
                  </CTableRow>
                ))}
              </CTableBody>
            </CTable>
          )}
        </CModalBody>
        <CModalFooter>
          <CButton color="secondary" onClick={() => setShowCustomersModal(false)}>
            Close
          </CButton>
        </CModalFooter>
      </CModal>
    </>
  );
};

export default Agents;
