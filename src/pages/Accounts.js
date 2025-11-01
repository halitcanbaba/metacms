/**
 * MT5 Accounts Page - List and Create accounts
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CButton,
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CForm,
  CFormInput,
  CFormLabel,
  CFormSelect,
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
  CDropdown,
  CDropdownToggle,
  CDropdownMenu,
  CDropdownItem,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilPlus, cilReload, cilSettings, cilLockLocked, cilUser } from '@coreui/icons';
import { accountsService } from '../services/accounts';
import { customersService } from '../services/customers';
import { getAgents } from '../services/agents';
import api from '../services/api';

const Accounts = () => {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [realtimeData, setRealtimeData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [agents, setAgents] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [createMode, setCreateMode] = useState('existing'); // 'existing' or 'new'
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Action modals
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showInvestorPasswordModal, setShowInvestorPasswordModal] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  
  // Action form data
  const [actionFormData, setActionFormData] = useState({
    newGroup: '',
    newPassword: '',
    confirmPassword: '',
    investorPassword: '',
    confirmInvestorPassword: '',
  });

  // Form state
  const [formData, setFormData] = useState({
    // Existing customer
    customer_id: '',
    // New customer
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    agent_id: '',
    // MT5 Account
    group: 'demo\\standard',
    leverage: 100,
    currency: 'USD',
    password: '',
    name: '',
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [accountsData, customersData, agentsData, groupsData, realtimeResponse] = await Promise.all([
        accountsService.getAll({ limit: 100 }),
        customersService.getAll({ limit: 100 }),
        getAgents({ limit: 100, active_only: true }),
        accountsService.getGroups(),
        api.get('/api/accounts/realtime'),
      ]);
      setAccounts(accountsData.items || []);
      setCustomers(customersData.items || []);
      setAgents(agentsData.items || []);
      setGroups(groupsData || []);
      setRealtimeData(realtimeResponse.data || []);
    } catch (err) {
      setError('Failed to load data: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, []); // Empty deps - this function doesn't depend on any props or state

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenModal = () => {
    setCreateMode('new'); // Default to "Create New Customer"
    setFormData({
      customer_id: '',
      customer_name: '',
      customer_email: '',
      customer_phone: '',
      agent_id: '',
      group: groups.length > 0 ? groups[0].name : 'demo\\standard',
      leverage: 100,
      currency: 'USD',
      password: '',
      name: '',
    });
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      // Prepare the payload based on mode
      const payload = {
        group: formData.group,
        leverage: parseInt(formData.leverage),
        currency: formData.currency,
        password: formData.password,
        name: formData.name,
      };

      if (createMode === 'existing') {
        // Use existing customer
        payload.customer_id = parseInt(formData.customer_id);
      } else {
        // Create new customer
        payload.customer_name = formData.customer_name;
        payload.customer_email = formData.customer_email;
        payload.customer_phone = formData.customer_phone;
        payload.agent_id = parseInt(formData.agent_id);
      }

      await accountsService.create(payload);
      setSuccess('MT5 Account created successfully!');
      handleCloseModal();
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create account');
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => {
      const updated = { ...prev, [name]: value };
      
      // Auto-sync: When customer_name changes, also update name and generate password
      if (name === 'customer_name') {
        updated.name = normalizeTurkishChars(value); // Full name without Turkish chars
        updated.password = generatePassword(value); // Auto-generate password
      }
      
      return updated;
    });
  };

  // Convert Turkish characters to English
  const normalizeTurkishChars = (text) => {
    if (!text) return '';
    
    const turkishMap = {
      'ç': 'c', 'Ç': 'C',
      'ğ': 'g', 'Ğ': 'G',
      'ı': 'i', 'İ': 'I',
      'ö': 'o', 'Ö': 'O',
      'ş': 's', 'Ş': 'S',
      'ü': 'u', 'Ü': 'U',
    };
    
    return text.replace(/[çÇğĞıİöÖşŞüÜ]/g, (match) => turkishMap[match] || match);
  };

  // Generate secure password from customer name
  const generatePassword = (customerName) => {
    if (!customerName || customerName.length < 3) {
      return '';
    }
    
    // Remove spaces, convert Turkish chars to English, take first 8 chars
    const normalized = normalizeTurkishChars(customerName);
    const cleanName = normalized.replace(/\s+/g, '').slice(0, 8).trim();
    if (!cleanName) return '';
    
    // Capitalize first letter, lowercase rest
    const capitalized = cleanName.charAt(0).toUpperCase() + cleanName.slice(1).toLowerCase();
    
    // Add number and symbol for security
    const number = Math.floor(Math.random() * 10); // 0-9
    const symbols = ['!', '@', '#', '$', '%', '&', '*'];
    const symbol = symbols[Math.floor(Math.random() * symbols.length)];
    
    return `${capitalized}${number}${symbol}`;
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'success';
      case 'disabled':
        return 'danger';
      default:
        return 'secondary';
    }
  };

  const getEquityForAccount = (login) => {
    const realtimeAccount = realtimeData.find(rt => rt.login === login);
    return realtimeAccount?.equity || 0;
  };

  const getNameForAccount = (login) => {
    const realtimeAccount = realtimeData.find(rt => rt.login === login);
    return realtimeAccount?.name || '-';
  };

  const formatNumber = (value) => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value || 0);
  };

  const handleRowClick = (login) => {
    navigate(`/account/${login}`);
  };

  // Action handlers
  const handleOpenGroupModal = (account, e) => {
    e.stopPropagation();
    setSelectedAccount(account);
    setActionFormData({ ...actionFormData, newGroup: account.group });
    setShowGroupModal(true);
  };

  const handleOpenPasswordModal = (account, e) => {
    e.stopPropagation();
    setSelectedAccount(account);
    setActionFormData({ ...actionFormData, newPassword: '', confirmPassword: '' });
    setShowPasswordModal(true);
  };

  const handleOpenInvestorPasswordModal = (account, e) => {
    e.stopPropagation();
    setSelectedAccount(account);
    setActionFormData({ ...actionFormData, investorPassword: '', confirmInvestorPassword: '' });
    setShowInvestorPasswordModal(true);
  };

  const handleActionInputChange = (e) => {
    const { name, value } = e.target;
    setActionFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleChangeGroup = async (e) => {
    e.preventDefault();
    if (!selectedAccount) return;

    try {
      setActionLoading(true);
      setError('');
      await api.put(`/api/accounts/${selectedAccount.login}/group`, {
        new_group: actionFormData.newGroup
      });
      setSuccess(`Group changed successfully for account ${selectedAccount.login}`);
      setShowGroupModal(false);
      loadData();
    } catch (err) {
      setError('Failed to change group: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (!selectedAccount) return;

    if (actionFormData.newPassword !== actionFormData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (actionFormData.newPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    try {
      setActionLoading(true);
      setError('');
      await api.put(`/api/accounts/${selectedAccount.login}/password`, {
        new_password: actionFormData.newPassword
      });
      setSuccess(`Password changed successfully for account ${selectedAccount.login}`);
      setShowPasswordModal(false);
      setActionFormData({ ...actionFormData, newPassword: '', confirmPassword: '' });
    } catch (err) {
      setError('Failed to change password: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  const handleChangeInvestorPassword = async (e) => {
    e.preventDefault();
    if (!selectedAccount) return;

    if (actionFormData.investorPassword !== actionFormData.confirmInvestorPassword) {
      setError('Passwords do not match');
      return;
    }

    if (actionFormData.investorPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    try {
      setActionLoading(true);
      setError('');
      await api.put(`/api/accounts/${selectedAccount.login}/investor-password`, {
        new_password: actionFormData.investorPassword
      });
      setSuccess(`Investor password changed successfully for account ${selectedAccount.login}`);
      setShowInvestorPasswordModal(false);
      setActionFormData({ ...actionFormData, investorPassword: '', confirmInvestorPassword: '' });
    } catch (err) {
      setError('Failed to change investor password: ' + (err.response?.data?.detail || err.message));
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <>
      <CRow>
        <CCol>
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

          <CCard>
            <CCardHeader>
              <CRow className="align-items-center">
                <CCol>
                  <strong>Account List</strong>
                </CCol>
                <CCol xs="auto">
                  <CButton color="secondary" className="me-2" onClick={loadData}>
                    <CIcon icon={cilReload} className="me-2" />
                    Refresh
                  </CButton>
                  <CButton color="primary" onClick={handleOpenModal}>
                    <CIcon icon={cilPlus} className="me-2" />
                    Create Account
                  </CButton>
                </CCol>
              </CRow>
            </CCardHeader>

            <CCardBody>
              {loading ? (
                <div className="text-center py-5">
                  <CSpinner color="primary" />
                </div>
              ) : accounts.length === 0 ? (
                <div className="text-center py-5 text-muted">
                  <p>No accounts found.</p>
                  <CButton color="primary" onClick={handleOpenModal}>
                    Create your first account
                  </CButton>
                </div>
              ) : (
                <CTable hover responsive>
                  <CTableHead>
                    <CTableRow>
                      <CTableHeaderCell>Login</CTableHeaderCell>
                      <CTableHeaderCell>Name</CTableHeaderCell>
                      <CTableHeaderCell>Customer</CTableHeaderCell>
                      <CTableHeaderCell>Agent</CTableHeaderCell>
                      <CTableHeaderCell>Group</CTableHeaderCell>
                      <CTableHeaderCell>Balance</CTableHeaderCell>
                      <CTableHeaderCell>Equity</CTableHeaderCell>
                      <CTableHeaderCell>Leverage</CTableHeaderCell>
                      <CTableHeaderCell>Currency</CTableHeaderCell>
                      <CTableHeaderCell>Status</CTableHeaderCell>
                      <CTableHeaderCell>Created</CTableHeaderCell>
                      <CTableHeaderCell>Actions</CTableHeaderCell>
                    </CTableRow>
                  </CTableHead>
                  <CTableBody>
                    {accounts.map((account) => {
                      const equity = getEquityForAccount(account.login);
                      const name = getNameForAccount(account.login);
                      return (
                        <CTableRow 
                          key={account.login}
                          onClick={() => handleRowClick(account.login)}
                          style={{ cursor: 'pointer' }}
                        >
                          <CTableDataCell>
                            <strong>{account.login}</strong>
                          </CTableDataCell>
                          <CTableDataCell>{name}</CTableDataCell>
                          <CTableDataCell>{account.customer?.name || '-'}</CTableDataCell>
                          <CTableDataCell>{account.customer?.agent?.name || '-'}</CTableDataCell>
                          <CTableDataCell>{account.group}</CTableDataCell>
                          <CTableDataCell>
                            {formatNumber(account.balance)}
                          </CTableDataCell>
                          <CTableDataCell>
                            {formatNumber(equity)}
                          </CTableDataCell>
                          <CTableDataCell>1:{account.leverage}</CTableDataCell>
                          <CTableDataCell>{account.currency}</CTableDataCell>
                          <CTableDataCell>
                            <CBadge color={getStatusColor(account.status)}>
                              {account.status || 'Unknown'}
                            </CBadge>
                          </CTableDataCell>
                          <CTableDataCell>
                            {new Date(account.created_at).toLocaleDateString()}
                          </CTableDataCell>
                          <CTableDataCell onClick={(e) => e.stopPropagation()}>
                            <CDropdown>
                              <CDropdownToggle color="secondary" size="sm">
                                <CIcon icon={cilSettings} /> Actions
                              </CDropdownToggle>
                              <CDropdownMenu>
                                <CDropdownItem onClick={(e) => handleOpenGroupModal(account, e)}>
                                  <CIcon icon={cilSettings} className="me-2" />
                                  Change Group
                                </CDropdownItem>
                                <CDropdownItem onClick={(e) => handleOpenPasswordModal(account, e)}>
                                  <CIcon icon={cilLockLocked} className="me-2" />
                                  Change Password
                                </CDropdownItem>
                                <CDropdownItem onClick={(e) => handleOpenInvestorPasswordModal(account, e)}>
                                  <CIcon icon={cilUser} className="me-2" />
                                  Change Investor Password
                                </CDropdownItem>
                              </CDropdownMenu>
                            </CDropdown>
                          </CTableDataCell>
                        </CTableRow>
                      );
                    })}
                  </CTableBody>
                </CTable>
              )}
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>

      {/* Create Modal */}
      <CModal visible={showModal} onClose={handleCloseModal} size="lg">
        <CModalHeader>
          <CModalTitle>Create MT5 Account</CModalTitle>
        </CModalHeader>
        <CForm onSubmit={handleSubmit}>
          <CModalBody>
            {/* Customer Selection Mode */}
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>Customer Selection</CFormLabel>
                <CFormSelect
                  value={createMode}
                  onChange={(e) => setCreateMode(e.target.value)}
                >
                  <option value="new">Create New Customer</option>
                  <option value="existing">Use Existing Customer</option>
                </CFormSelect>
              </CCol>
            </CRow>

            {createMode === 'existing' ? (
              // Existing Customer
              <CRow className="mb-3">
                <CCol>
                  <CFormLabel>Customer *</CFormLabel>
                  <CFormSelect
                    name="customer_id"
                    value={formData.customer_id}
                    onChange={handleInputChange}
                    required
                  >
                    <option value="">Select Customer</option>
                    {customers.map((customer) => (
                      <option key={customer.id} value={customer.id}>
                        {customer.name} ({customer.email})
                      </option>
                    ))}
                  </CFormSelect>
                </CCol>
              </CRow>
            ) : (
              // New Customer Fields
              <>
                <CRow className="mb-3">
                  <CCol md={6}>
                    <CFormLabel>Customer Name *</CFormLabel>
                    <CFormInput
                      name="customer_name"
                      value={formData.customer_name}
                      onChange={handleInputChange}
                      placeholder="John Doe"
                      required
                    />
                  </CCol>
                  <CCol md={6}>
                    <CFormLabel>Customer Email *</CFormLabel>
                    <CFormInput
                      type="email"
                      name="customer_email"
                      value={formData.customer_email}
                      onChange={handleInputChange}
                      placeholder="john@example.com"
                      required
                    />
                  </CCol>
                </CRow>

                <CRow className="mb-3">
                  <CCol md={6}>
                    <CFormLabel>Customer Phone</CFormLabel>
                    <CFormInput
                      type="tel"
                      name="customer_phone"
                      value={formData.customer_phone}
                      onChange={handleInputChange}
                      placeholder="+1234567890"
                    />
                  </CCol>
                  <CCol md={6}>
                    <CFormLabel>Agent *</CFormLabel>
                    <CFormSelect
                      name="agent_id"
                      value={formData.agent_id}
                      onChange={handleInputChange}
                      required
                    >
                      <option value="">Select Agent</option>
                      {agents.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name} ({agent.email})
                        </option>
                      ))}
                    </CFormSelect>
                  </CCol>
                </CRow>
              </>
            )}

            <hr />

            {/* MT5 Account Fields */}
            <CRow className="mb-3">
              <CCol md={6}>
                <CFormLabel>Full Name *</CFormLabel>
                <CFormInput
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="Customer's full name (auto-filled)"
                  required
                  disabled={createMode === 'new'} // Auto-filled from customer name
                />
                {createMode === 'new' && (
                  <small className="text-muted">Auto-synced with Customer Name</small>
                )}
              </CCol>
              <CCol md={6}>
                <CFormLabel>Password *</CFormLabel>
                <div className="d-flex gap-2">
                  <CFormInput
                    type="text"
                    name="password"
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder="Min 8 chars (auto-generated)"
                    required
                  />
                  <CButton 
                    color="secondary" 
                    variant="outline"
                    onClick={() => {
                      const newPassword = generatePassword(formData.customer_name || 'User');
                      setFormData(prev => ({ ...prev, password: newPassword }));
                    }}
                    disabled={!formData.customer_name && createMode === 'new'}
                  >
                    Generate
                  </CButton>
                </div>
                <small className="text-muted">
                  Must contain: uppercase, lowercase, number, symbol
                </small>
              </CCol>
            </CRow>

            <CRow className="mb-3">
              <CCol md={4}>
                <CFormLabel>Group *</CFormLabel>
                <CFormSelect
                  name="group"
                  value={formData.group}
                  onChange={handleInputChange}
                  required
                >
                  <option value="">Select Group</option>
                  {groups.map((group) => (
                    <option key={group.name} value={group.name}>
                      {group.name}
                    </option>
                  ))}
                </CFormSelect>
              </CCol>
              <CCol md={4}>
                <CFormLabel>Leverage *</CFormLabel>
                <CFormSelect
                  name="leverage"
                  value={formData.leverage}
                  onChange={handleInputChange}
                  required
                >
                  <option value="50">1:50</option>
                  <option value="100">1:100</option>
                  <option value="200">1:200</option>
                  <option value="500">1:500</option>
                  <option value="1000">1:1000</option>
                </CFormSelect>
              </CCol>
              <CCol md={4}>
                <CFormLabel>Currency *</CFormLabel>
                <CFormSelect
                  name="currency"
                  value={formData.currency}
                  onChange={handleInputChange}
                  required
                >
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                </CFormSelect>
              </CCol>
            </CRow>
          </CModalBody>
          <CModalFooter>
            <CButton color="secondary" onClick={handleCloseModal}>
              Cancel
            </CButton>
            <CButton color="primary" type="submit">
              Create Account
            </CButton>
          </CModalFooter>
        </CForm>
      </CModal>

      {/* Change Group Modal */}
      <CModal visible={showGroupModal} onClose={() => setShowGroupModal(false)}>
        <CModalHeader>
          <CModalTitle>Change Group - Account {selectedAccount?.login}</CModalTitle>
        </CModalHeader>
        <CForm onSubmit={handleChangeGroup}>
          <CModalBody>
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>Current Group</CFormLabel>
                <CFormInput value={selectedAccount?.group || ''} disabled />
              </CCol>
            </CRow>
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>New Group *</CFormLabel>
                <CFormSelect
                  name="newGroup"
                  value={actionFormData.newGroup}
                  onChange={handleActionInputChange}
                  required
                >
                  {groups.map((group) => (
                    <option key={group.name} value={group.name}>
                      {group.name}
                    </option>
                  ))}
                </CFormSelect>
              </CCol>
            </CRow>
          </CModalBody>
          <CModalFooter>
            <CButton color="secondary" onClick={() => setShowGroupModal(false)} disabled={actionLoading}>
              Cancel
            </CButton>
            <CButton color="primary" type="submit" disabled={actionLoading}>
              {actionLoading ? <CSpinner size="sm" /> : 'Change Group'}
            </CButton>
          </CModalFooter>
        </CForm>
      </CModal>

      {/* Change Password Modal */}
      <CModal visible={showPasswordModal} onClose={() => setShowPasswordModal(false)}>
        <CModalHeader>
          <CModalTitle>Change Password - Account {selectedAccount?.login}</CModalTitle>
        </CModalHeader>
        <CForm onSubmit={handleChangePassword}>
          <CModalBody>
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>New Password *</CFormLabel>
                <CFormInput
                  type="password"
                  name="newPassword"
                  value={actionFormData.newPassword}
                  onChange={handleActionInputChange}
                  placeholder="Enter new password"
                  minLength={6}
                  required
                />
                <small className="text-muted">Minimum 6 characters</small>
              </CCol>
            </CRow>
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>Confirm Password *</CFormLabel>
                <CFormInput
                  type="password"
                  name="confirmPassword"
                  value={actionFormData.confirmPassword}
                  onChange={handleActionInputChange}
                  placeholder="Confirm new password"
                  minLength={6}
                  required
                />
              </CCol>
            </CRow>
          </CModalBody>
          <CModalFooter>
            <CButton color="secondary" onClick={() => setShowPasswordModal(false)} disabled={actionLoading}>
              Cancel
            </CButton>
            <CButton color="primary" type="submit" disabled={actionLoading}>
              {actionLoading ? <CSpinner size="sm" /> : 'Change Password'}
            </CButton>
          </CModalFooter>
        </CForm>
      </CModal>

      {/* Change Investor Password Modal */}
      <CModal visible={showInvestorPasswordModal} onClose={() => setShowInvestorPasswordModal(false)}>
        <CModalHeader>
          <CModalTitle>Change Investor Password - Account {selectedAccount?.login}</CModalTitle>
        </CModalHeader>
        <CForm onSubmit={handleChangeInvestorPassword}>
          <CModalBody>
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>New Investor Password *</CFormLabel>
                <CFormInput
                  type="password"
                  name="investorPassword"
                  value={actionFormData.investorPassword}
                  onChange={handleActionInputChange}
                  placeholder="Enter new investor password"
                  minLength={6}
                  required
                />
                <small className="text-muted">Minimum 6 characters (Read-only access)</small>
              </CCol>
            </CRow>
            <CRow className="mb-3">
              <CCol>
                <CFormLabel>Confirm Investor Password *</CFormLabel>
                <CFormInput
                  type="password"
                  name="confirmInvestorPassword"
                  value={actionFormData.confirmInvestorPassword}
                  onChange={handleActionInputChange}
                  placeholder="Confirm new investor password"
                  minLength={6}
                  required
                />
              </CCol>
            </CRow>
          </CModalBody>
          <CModalFooter>
            <CButton color="secondary" onClick={() => setShowInvestorPasswordModal(false)} disabled={actionLoading}>
              Cancel
            </CButton>
            <CButton color="primary" type="submit" disabled={actionLoading}>
              {actionLoading ? <CSpinner size="sm" /> : 'Change Investor Password'}
            </CButton>
          </CModalFooter>
        </CForm>
      </CModal>
    </>
  );
};

export default Accounts;
