import React, { useState, useEffect } from 'react';
import {
  CCard,
  CCardBody,
  CCardHeader,
  CCol,
  CRow,
  CTable,
  CTableHead,
  CTableRow,
  CTableHeaderCell,
  CTableBody,
  CTableDataCell,
  CButton,
  CModal,
  CModalHeader,
  CModalTitle,
  CModalBody,
  CModalFooter,
  CForm,
  CFormLabel,
  CFormInput,
  CFormSelect,
  CFormSwitch,
  CSpinner,
  CBadge,
  CInputGroup,
  CInputGroupText,
  CPagination,
  CPaginationItem,
} from '@coreui/react';
import CIcon from '@coreui/icons-react';
import { cilPencil, cilTrash, cilUserPlus, cilSearch, cilLockLocked, cilPeople } from '@coreui/icons';
import api from '../services/api';

const Users = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [deletingUser, setDeletingUser] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    role: 'viewer',
    is_active: true,
  });
  const [formErrors, setFormErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const usersPerPage = 10;

  useEffect(() => {
    fetchUsers();
  }, [currentPage, searchTerm]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const skip = (currentPage - 1) * usersPerPage;
      const params = {
        skip,
        limit: usersPerPage,
      };
      if (searchTerm) {
        params.search = searchTerm;
      }
      const response = await api.get('/api/users', { params });
      setUsers(response.data.users || []);
      setTotalUsers(response.data.total || 0);
    } catch (error) {
      console.error('Error fetching users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenModal = (user = null) => {
    if (user) {
      setEditingUser(user);
      setFormData({
        email: user.email,
        password: '',
        full_name: user.full_name || '',
        role: user.role,
        is_active: user.is_active,
      });
    } else {
      setEditingUser(null);
      setFormData({
        email: '',
        password: '',
        full_name: '',
        role: 'viewer',
        is_active: true,
      });
    }
    setFormErrors({});
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingUser(null);
    setFormData({
      email: '',
      password: '',
      full_name: '',
      role: 'viewer',
      is_active: true,
    });
    setFormErrors({});
  };

  const validateForm = () => {
    const errors = {};
    
    if (!formData.email) {
      errors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      errors.email = 'Email is invalid';
    }
    
    if (!editingUser && !formData.password) {
      errors.password = 'Password is required';
    } else if (formData.password && formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    }
    
    if (!formData.full_name) {
      errors.full_name = 'Full name is required';
    }
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        email: formData.email,
        full_name: formData.full_name,
        role: formData.role,
        is_active: formData.is_active,
      };
      
      if (formData.password) {
        payload.password = formData.password;
      }

      if (editingUser) {
        await api.put(`/api/users/${editingUser.id}`, payload);
      } else {
        await api.post('/api/users', payload);
      }
      
      handleCloseModal();
      fetchUsers();
    } catch (error) {
      console.error('Error saving user:', error);
      if (error.response?.data?.detail) {
        if (error.response.data.detail.includes('email')) {
          setFormErrors({ email: 'Email already exists' });
        } else {
          alert(error.response.data.detail);
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenDeleteModal = (user) => {
    setDeletingUser(user);
    setShowDeleteModal(true);
  };

  const handleCloseDeleteModal = () => {
    setShowDeleteModal(false);
    setDeletingUser(null);
  };

  const handleDelete = async () => {
    if (!deletingUser) return;
    
    setSubmitting(true);
    try {
      await api.delete(`/api/users/${deletingUser.id}`);
      handleCloseDeleteModal();
      fetchUsers();
    } catch (error) {
      console.error('Error deleting user:', error);
      if (error.response?.data?.detail) {
        alert(error.response.data.detail);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1);
  };

  const getRoleBadge = (role) => {
    const colors = {
      admin: 'danger',
      manager: 'warning',
      viewer: 'info',
    };
    return <CBadge color={colors[role] || 'secondary'}>{role}</CBadge>;
  };

  const totalPages = Math.ceil(totalUsers / usersPerPage);

  return (
    <CRow>
      <CCol xs={12}>
        <CCard className="mb-4">
          <CCardHeader className="d-flex justify-content-between align-items-center">
            <div className="d-flex align-items-center">
              <CIcon icon={cilPeople} className="me-2" />
              <strong>User Management</strong>
            </div>
            <CButton color="primary" onClick={() => handleOpenModal()}>
              <CIcon icon={cilUserPlus} className="me-2" />
              Create User
            </CButton>
          </CCardHeader>
          <CCardBody>
            <div className="mb-3">
              <CInputGroup style={{ maxWidth: '400px' }}>
                <CInputGroupText>
                  <CIcon icon={cilSearch} />
                </CInputGroupText>
                <CFormInput
                  placeholder="Search by email or name..."
                  value={searchTerm}
                  onChange={handleSearchChange}
                />
              </CInputGroup>
            </div>

            {loading ? (
              <div className="text-center py-5">
                <CSpinner color="primary" />
              </div>
            ) : (
              <>
                <CTable striped hover responsive>
                  <CTableHead>
                    <CTableRow>
                      <CTableHeaderCell>ID</CTableHeaderCell>
                      <CTableHeaderCell>Email</CTableHeaderCell>
                      <CTableHeaderCell>Full Name</CTableHeaderCell>
                      <CTableHeaderCell>Role</CTableHeaderCell>
                      <CTableHeaderCell>Status</CTableHeaderCell>
                      <CTableHeaderCell>Created</CTableHeaderCell>
                      <CTableHeaderCell className="text-center">Actions</CTableHeaderCell>
                    </CTableRow>
                  </CTableHead>
                  <CTableBody>
                    {users.length === 0 ? (
                      <CTableRow>
                        <CTableDataCell colSpan="7" className="text-center">
                          No users found
                        </CTableDataCell>
                      </CTableRow>
                    ) : (
                      users.map((user) => (
                        <CTableRow key={user.id}>
                          <CTableDataCell>{user.id}</CTableDataCell>
                          <CTableDataCell>{user.email}</CTableDataCell>
                          <CTableDataCell>{user.full_name || '-'}</CTableDataCell>
                          <CTableDataCell>{getRoleBadge(user.role)}</CTableDataCell>
                          <CTableDataCell>
                            {user.is_active ? (
                              <CBadge color="success">Active</CBadge>
                            ) : (
                              <CBadge color="secondary">Inactive</CBadge>
                            )}
                          </CTableDataCell>
                          <CTableDataCell>
                            {new Date(user.created_at).toLocaleDateString()}
                          </CTableDataCell>
                          <CTableDataCell className="text-center">
                            <CButton
                              color="info"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenModal(user)}
                              className="me-2"
                            >
                              <CIcon icon={cilPencil} />
                            </CButton>
                            <CButton
                              color="danger"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenDeleteModal(user)}
                            >
                              <CIcon icon={cilTrash} />
                            </CButton>
                          </CTableDataCell>
                        </CTableRow>
                      ))
                    )}
                  </CTableBody>
                </CTable>

                {totalPages > 1 && (
                  <CPagination className="mt-3 justify-content-center">
                    <CPaginationItem
                      disabled={currentPage === 1}
                      onClick={() => setCurrentPage(currentPage - 1)}
                    >
                      Previous
                    </CPaginationItem>
                    {[...Array(totalPages)].map((_, index) => (
                      <CPaginationItem
                        key={index + 1}
                        active={currentPage === index + 1}
                        onClick={() => setCurrentPage(index + 1)}
                      >
                        {index + 1}
                      </CPaginationItem>
                    ))}
                    <CPaginationItem
                      disabled={currentPage === totalPages}
                      onClick={() => setCurrentPage(currentPage + 1)}
                    >
                      Next
                    </CPaginationItem>
                  </CPagination>
                )}
              </>
            )}
          </CCardBody>
        </CCard>
      </CCol>

      {/* Create/Edit Modal */}
      <CModal visible={showModal} onClose={handleCloseModal} size="lg">
        <CModalHeader>
          <CModalTitle>{editingUser ? 'Edit User' : 'Create New User'}</CModalTitle>
        </CModalHeader>
        <CModalBody>
          <CForm onSubmit={handleSubmit}>
            <div className="mb-3">
              <CFormLabel htmlFor="email">Email *</CFormLabel>
              <CFormInput
                type="email"
                id="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                invalid={!!formErrors.email}
                feedback={formErrors.email}
              />
            </div>

            <div className="mb-3">
              <CFormLabel htmlFor="password">
                <CIcon icon={cilLockLocked} className="me-2" />
                Password {!editingUser && '*'}
              </CFormLabel>
              <CFormInput
                type="password"
                id="password"
                placeholder={editingUser ? 'Leave empty to keep current password' : 'Enter password'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                invalid={!!formErrors.password}
                feedback={formErrors.password}
              />
              <small className="text-muted">Minimum 8 characters</small>
            </div>

            <div className="mb-3">
              <CFormLabel htmlFor="full_name">Full Name *</CFormLabel>
              <CFormInput
                type="text"
                id="full_name"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                invalid={!!formErrors.full_name}
                feedback={formErrors.full_name}
              />
            </div>

            <div className="mb-3">
              <CFormLabel htmlFor="role">Role *</CFormLabel>
              <CFormSelect
                id="role"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              >
                <option value="viewer">Viewer</option>
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
              </CFormSelect>
            </div>

            <div className="mb-3">
              <CFormSwitch
                id="is_active"
                label="Active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
            </div>
          </CForm>
        </CModalBody>
        <CModalFooter>
          <CButton color="secondary" onClick={handleCloseModal} disabled={submitting}>
            Cancel
          </CButton>
          <CButton color="primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <CSpinner size="sm" /> : editingUser ? 'Update User' : 'Create User'}
          </CButton>
        </CModalFooter>
      </CModal>

      {/* Delete Confirmation Modal */}
      <CModal visible={showDeleteModal} onClose={handleCloseDeleteModal}>
        <CModalHeader>
          <CModalTitle>Confirm Delete</CModalTitle>
        </CModalHeader>
        <CModalBody>
          Are you sure you want to delete user <strong>{deletingUser?.email}</strong>?
          This action cannot be undone.
        </CModalBody>
        <CModalFooter>
          <CButton color="secondary" onClick={handleCloseDeleteModal} disabled={submitting}>
            Cancel
          </CButton>
          <CButton color="danger" onClick={handleDelete} disabled={submitting}>
            {submitting ? <CSpinner size="sm" /> : 'Delete User'}
          </CButton>
        </CModalFooter>
      </CModal>
    </CRow>
  );
};

export default Users;
