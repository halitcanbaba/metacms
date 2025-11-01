/**
 * Customers Page - List, Create, Edit, Delete customers
 */
import React, { useEffect, useState } from 'react';
import {
  CButton,
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CForm,
  CFormInput,
  CFormLabel,
  CFormTextarea,
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
import { cilPlus, cilPencil, cilTrash, cilSearch, cilReload } from '@coreui/icons';
import { customersService } from '../services/customers';

const Customers = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    address: '',
    notes: '',
  });

  useEffect(() => {
    loadCustomers();
  }, []);

  const loadCustomers = async (searchTerm = '') => {
    try {
      setLoading(true);
      setError('');
      const data = await customersService.getAll({
        search: searchTerm || undefined,
        limit: 100,
      });
      setCustomers(data.items || []);
    } catch (err) {
      setError('Failed to load customers: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    loadCustomers(search);
  };

  const handleOpenModal = (customer = null) => {
    if (customer) {
      setEditingCustomer(customer);
      setFormData({
        name: customer.name || '',
        email: customer.email || '',
        phone: customer.phone || '',
        address: customer.address || '',
        notes: customer.notes || '',
      });
    } else {
      setEditingCustomer(null);
      setFormData({
        name: '',
        email: '',
        phone: '',
        address: '',
        notes: '',
      });
    }
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingCustomer(null);
    setFormData({
      name: '',
      email: '',
      phone: '',
      address: '',
      notes: '',
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingCustomer) {
        await customersService.update(editingCustomer.id, formData);
        setSuccess('Customer updated successfully!');
      } else {
        await customersService.create(formData);
        setSuccess('Customer created successfully!');
      }
      handleCloseModal();
      loadCustomers(search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Operation failed');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this customer?')) {
      return;
    }

    try {
      setError('');
      await customersService.delete(id);
      setSuccess('Customer deleted successfully!');
      loadCustomers(search);
    } catch (err) {
      setError(err.response?.data?.detail || 'Delete failed');
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
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
                  <strong>Customer List</strong>
                </CCol>
                <CCol xs="auto">
                  <CButton color="primary" onClick={() => handleOpenModal()}>
                    <CIcon icon={cilPlus} className="me-2" />
                    Add Customer
                  </CButton>
                </CCol>
              </CRow>
            </CCardHeader>

            <CCardBody>
              {/* Search Bar */}
              <CRow className="mb-3">
                <CCol md={6}>
                  <CInputGroup>
                    <CFormInput
                      placeholder="Search by name, email, or phone..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                    />
                    <CButton color="primary" onClick={handleSearch}>
                      <CIcon icon={cilSearch} />
                    </CButton>
                    <CButton color="secondary" onClick={() => loadCustomers()}>
                      <CIcon icon={cilReload} />
                    </CButton>
                  </CInputGroup>
                </CCol>
              </CRow>

              {/* Table */}
              {loading ? (
                <div className="text-center py-5">
                  <CSpinner color="primary" />
                </div>
              ) : customers.length === 0 ? (
                <div className="text-center py-5 text-muted">
                  <p>No customers found.</p>
                  <CButton color="primary" onClick={() => handleOpenModal()}>
                    Create your first customer
                  </CButton>
                </div>
              ) : (
                <CTable hover responsive>
                  <CTableHead>
                    <CTableRow>
                      <CTableHeaderCell>ID</CTableHeaderCell>
                      <CTableHeaderCell>Name</CTableHeaderCell>
                      <CTableHeaderCell>Email</CTableHeaderCell>
                      <CTableHeaderCell>Phone</CTableHeaderCell>
                      <CTableHeaderCell>MT5 Accounts</CTableHeaderCell>
                      <CTableHeaderCell>Created</CTableHeaderCell>
                      <CTableHeaderCell>Actions</CTableHeaderCell>
                    </CTableRow>
                  </CTableHead>
                  <CTableBody>
                    {customers.map((customer) => (
                      <CTableRow key={customer.id}>
                        <CTableDataCell>{customer.id}</CTableDataCell>
                        <CTableDataCell>
                          <strong>{customer.name}</strong>
                        </CTableDataCell>
                        <CTableDataCell>{customer.email}</CTableDataCell>
                        <CTableDataCell>{customer.phone || '-'}</CTableDataCell>
                        <CTableDataCell>
                          <CBadge color="info">
                            {customer.mt5_accounts?.length || 0} accounts
                          </CBadge>
                        </CTableDataCell>
                        <CTableDataCell>
                          {new Date(customer.created_at).toLocaleDateString()}
                        </CTableDataCell>
                        <CTableDataCell>
                          <CButton
                            color="info"
                            size="sm"
                            className="me-2"
                            onClick={() => handleOpenModal(customer)}
                          >
                            <CIcon icon={cilPencil} />
                          </CButton>
                          <CButton
                            color="danger"
                            size="sm"
                            onClick={() => handleDelete(customer.id)}
                          >
                            <CIcon icon={cilTrash} />
                          </CButton>
                        </CTableDataCell>
                      </CTableRow>
                    ))}
                  </CTableBody>
                </CTable>
              )}
            </CCardBody>
          </CCard>
        </CCol>
      </CRow>

      {/* Create/Edit Modal */}
      <CModal visible={showModal} onClose={handleCloseModal} size="lg">
        <CModalHeader>
          <CModalTitle>{editingCustomer ? 'Edit Customer' : 'New Customer'}</CModalTitle>
        </CModalHeader>
        <CForm onSubmit={handleSubmit}>
          <CModalBody>
            <CRow className="mb-3">
              <CCol md={6}>
                <CFormLabel>Name *</CFormLabel>
                <CFormInput
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  required
                />
              </CCol>
              <CCol md={6}>
                <CFormLabel>Email *</CFormLabel>
                <CFormInput
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  required
                />
              </CCol>
            </CRow>

            <CRow className="mb-3">
              <CCol md={6}>
                <CFormLabel>Phone</CFormLabel>
                <CFormInput
                  name="phone"
                  value={formData.phone}
                  onChange={handleInputChange}
                />
              </CCol>
              <CCol md={6}>
                <CFormLabel>Address</CFormLabel>
                <CFormInput
                  name="address"
                  value={formData.address}
                  onChange={handleInputChange}
                />
              </CCol>
            </CRow>

            <CRow className="mb-3">
              <CCol>
                <CFormLabel>Notes</CFormLabel>
                <CFormTextarea
                  name="notes"
                  rows={3}
                  value={formData.notes}
                  onChange={handleInputChange}
                />
              </CCol>
            </CRow>
          </CModalBody>
          <CModalFooter>
            <CButton color="secondary" onClick={handleCloseModal}>
              Cancel
            </CButton>
            <CButton color="primary" type="submit">
              {editingCustomer ? 'Update' : 'Create'}
            </CButton>
          </CModalFooter>
        </CForm>
      </CModal>
    </>
  );
};

export default Customers;
